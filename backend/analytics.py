"""Phase 3 analytics engine (FR14-FR22).

Turns stored chat messages and feedback into the metrics, tables, chart data
and insights shown on the analytics dashboard, and builds the final summary
that is stored permanently when a session ends.
"""
from datetime import datetime
import pandas as pd
from topic_classifier import classifier, TOPICS, GENERAL, is_follow_up
from charts import build_figures, topic_colors, TEMPLATE
from chat_titles import fallback_title, fallback_subject

ALL_TOPICS = TOPICS + [GENERAL]
PHASES = ["Start", "Middle", "End"]
CORRECTNESS = {"correct": "Correct", "partial": "Partial", "incorrect": "Incorrect"}
# Accuracy counts a partial reply as half right.
CORRECTNESS_SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
LENGTH_TYPES = {"short": "Short", "to_the_point": "To the Point", "lengthy": "Lengthy"}
RATINGS = {1: "1", 2: "2", 3: "3", 4: "4"}

REPLY_TABLE_LIMIT = 200
TREND_LIMIT = 100
REPLY_COLUMNS = ["message_id", "session_id", "timestamp", "question", "topic", "subject",
                 "response_time", "rating", "correctness", "length_type"]
SUBJECTS_PER_TOPIC = 5
# Summary of a group without replies, e.g. a phase no session has reached yet
EMPTY_SUMMARY = {"replies": 0, "rated": 0, "correct": 0, "partial": 0, "incorrect": 0,
                 "accuracy": None, "avg_rating": None, "avg_response_time": None}


def _round(value, digits=1):
    """Round to a plain float, or None when there is no value."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _percent(part, total):
    return _round(part / total * 100) if total else None


def _replies(count, prefix=""):
    return f"{count} {prefix}{'reply' if count == 1 else 'replies'}"


class AnalyticsEngine:
    def __init__(self, db):
        self.db = db

    # ============ FR14: DATA RETRIEVAL ============

    def load_replies(self, user_id, session_id=None):
        """One row per bot reply, joined with its question, topic and feedback"""
        messages = self.db.get_messages(user_id, session_id)
        feedback = self.db.feedback_by_message(user_id)

        rows = []
        last_question = {}
        last_topic = {}
        last_subject = {}
        for msg in messages:
            sid = msg.get("session_id")
            if msg.get("role") == "user":
                last_question[sid] = msg
                continue
            if msg.get("role") != "bot":
                continue

            question = last_question.pop(sid, None) or {}
            text = question.get("content", "")
            topic = msg.get("topic_label") or question.get("topic_label")
            if topic not in ALL_TOPICS:
                # Messages stored before the current classifier get labelled now (FR15).
                topic = classifier.classify(text, last_topic.get(sid))
            last_topic[sid] = topic

            # What the question is specifically about. Until the model names it, a quick version is used,
            # and a short follow-up ("give me an example") keeps the chat's previous subject.
            subject = question.get("subject") or (is_follow_up(text) and last_subject.get(sid)) or fallback_subject(text)
            last_subject[sid] = subject

            response_time = msg.get("response_time")
            if response_time is None and question.get("timestamp") and msg.get("timestamp"):
                response_time = (msg["timestamp"] - question["timestamp"]).total_seconds()

            item = feedback.get(str(msg["_id"]), {})
            rows.append({
                "message_id": str(msg["_id"]),
                "session_id": sid,
                "timestamp": msg.get("timestamp"),
                "question": text,
                "topic": topic,
                "subject": subject,
                "response_time": response_time,
                "rating": item.get("rating"),
                "correctness": item.get("correctness"),
                "length_type": item.get("length_type"),
            })

        df = pd.DataFrame(rows, columns=REPLY_COLUMNS)
        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["response_time"] = pd.to_numeric(df["response_time"], errors="coerce")
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df["rating"] = df["rating"].where(df["rating"].isin(list(RATINGS)))
        df["correctness"] = df["correctness"].where(df["correctness"].isin(list(CORRECTNESS)))
        df["length_type"] = df["length_type"].where(df["length_type"].isin(list(LENGTH_TYPES)))
        df["score"] = df["correctness"].map(CORRECTNESS_SCORE)
        return self.segment_sessions(df)

    # ============ FR16: SESSION SEGMENTATION ============

    @staticmethod
    def segment_sessions(df):
        """Number the replies of each session and split them into Start / Middle / End by position.

        A reply's position runs from 0 (first) to 1 (last) and is rounded to the nearest of
        Start, Middle and End, so the first reply is always Start and the last always End.
        A single-reply session is all Start.
        """
        df = df.sort_values(["session_id", "timestamp"]).reset_index(drop=True)
        df["turn"] = df.groupby("session_id", dropna=False).cumcount() + 1
        session_length = df.groupby("session_id", dropna=False)["turn"].transform("size")
        position = ((df["turn"] - 1) / (session_length - 1).where(session_length > 1, 1)).fillna(0)
        df["phase"] = (position * 2).round().astype(int).map(dict(enumerate(PHASES)))
        return df

    # ============ FR17, FR18: METRICS ============

    @staticmethod
    def _summaries(df, keys):
        """Replies, correctness counts, accuracy, rating and response time for each group of replies"""
        is_status = {status: df["correctness"].eq(status) for status in CORRECTNESS}
        stats = df.assign(**is_status).groupby(keys, sort=False).agg(
            replies=("correctness", "size"),
            rated=("correctness", "count"),
            **{status: (status, "sum") for status in CORRECTNESS},
            accuracy=("score", "mean"),
            avg_rating=("rating", "mean"),
            avg_response_time=("response_time", "mean"),
        )
        return {key: {
            "replies": int(row["replies"]),
            "rated": int(row["rated"]),
            **{status: int(row[status]) for status in CORRECTNESS},
            "accuracy": _round(row["accuracy"] * 100),
            "avg_rating": _round(row["avg_rating"], 2),
            "avg_response_time": _round(row["avg_response_time"], 2),
        } for key, row in stats.to_dict("index").items()}

    def _group_table(self, df, column, order, keep_empty=False):
        summaries = self._summaries(df, df[column])
        return [{column: key, **summaries.get(key, EMPTY_SUMMARY)}
                for key in order if key in summaries or keep_empty]

    @staticmethod
    def _correctness_summary(overall):
        rated = overall["rated"]
        return {
            "correct": overall["correct"],
            "partial": overall["partial"],
            "incorrect": overall["incorrect"],
            "rated": rated,
            "unrated": overall["replies"] - rated,
            "correct_pct": _percent(overall["correct"], rated),
            "partial_pct": _percent(overall["partial"], rated),
            "incorrect_pct": _percent(overall["incorrect"], rated),
            "accuracy": overall["accuracy"],
        }

    @staticmethod
    def _response_time_summary(df):
        times = df["response_time"].dropna()
        return {
            "count": int(len(times)),
            "mean": _round(times.mean(), 2),
            "median": _round(times.median(), 2),
            "min": _round(times.min(), 2),
            "max": _round(times.max(), 2),
            "std": _round(times.std(), 2),
            "p90": _round(times.quantile(0.9), 2),
        }

    @staticmethod
    def _distribution(series, labels):
        counts = series.value_counts()
        total = int(counts.sum())
        return [
            {"key": key, "label": label, "count": int(counts.get(key, 0)),
             "percent": _percent(int(counts.get(key, 0)), total)}
            for key, label in labels.items()
        ]

    @staticmethod
    def _strongest_and_weakest(topic_table):
        """Highest and lowest accuracy among rated topics; more rated replies breaks a tie"""
        rated = [row for row in topic_table if row["accuracy"] is not None]
        if not rated:
            return None, None
        best = max(rated, key=lambda row: (row["accuracy"], row["rated"]))
        worst = min(rated, key=lambda row: (row["accuracy"], -row["rated"]))
        return best, worst if worst is not best else None

    # ============ FR19: TABLES ============

    @staticmethod
    def _reply_table(df):
        latest = df.sort_values("timestamp", ascending=False).head(REPLY_TABLE_LIMIT)
        return [{
            "timestamp": row["timestamp"].isoformat() if pd.notna(row["timestamp"]) else None,
            "session_id": row["session_id"],
            "turn": int(row["turn"]),
            "phase": row["phase"],
            "topic": row["topic"],
            "subject": row["subject"],
            "question": str(row["question"])[:120],
            "rating": int(row["rating"]) if pd.notna(row["rating"]) else None,
            "correctness": CORRECTNESS.get(row["correctness"]),
            "length_type": LENGTH_TYPES.get(row["length_type"]),
            "response_time": _round(row["response_time"], 2),
        } for row in latest.to_dict("records")]

    @staticmethod
    def _first_questions(df):
        """Each session's first non-blank question, used as its title until the model's title is stored"""
        asked = df[df["question"].astype(str).str.strip() != ""]
        return asked.groupby("session_id")["question"].first()

    def session_table(self, df, ended_sessions, titles):
        """Session-level insights: one row per session, most recent first (FR21)"""
        groups = df.groupby("session_id", sort=False)
        started = groups["timestamp"].min()
        last_activity = groups["timestamp"].max()
        dominant_topic = groups["topic"].agg(lambda topics: topics.value_counts().index[0])
        # The first reply of a session counts as a switch from nothing, hence the -1.
        topic_switches = df["topic"].ne(groups["topic"].shift()).groupby(df["session_id"]).sum() - 1
        first_questions = self._first_questions(df)

        rows = []
        for sid, summary in self._summaries(df, df["session_id"]).items():
            ended_at = ended_sessions.get(sid)
            rows.append({
                "session_id": sid,
                "title": titles.get(sid) or fallback_title(first_questions.get(sid, "")),
                "started": started[sid].isoformat(),
                "last_activity": last_activity[sid].isoformat(),
                "dominant_topic": dominant_topic[sid],
                "topic_switches": int(topic_switches[sid]),
                "status": "Ended" if sid in ended_sessions else "Active",
                "ended_at": ended_at.isoformat() if isinstance(ended_at, datetime) else None,
                **summary,
            })
        rows.sort(key=lambda row: row["last_activity"], reverse=True)
        return rows

    # ============ FR20: GRAPH DATA ============

    @staticmethod
    def _chart_data(df, tables):
        turns = list(range(1, int(df["turn"].max()) + 1))
        per_turn = pd.crosstab(df["turn"], df["correctness"]).reindex(
            index=turns, columns=list(CORRECTNESS), fill_value=0
        )
        trend = df.dropna(subset=["response_time"]).sort_values("timestamp").tail(TREND_LIMIT)
        rated_topics = [row for row in tables["topic"] if row["accuracy"] is not None]

        return {
            "topic_distribution": {
                "labels": [row["topic"] for row in tables["topic"]],
                "values": [row["replies"] for row in tables["topic"]],
            },
            "accuracy_per_topic": {
                "labels": [row["topic"] for row in rated_topics],
                "values": [row["accuracy"] for row in rated_topics],
            },
            "accuracy_vs_phase": {
                "labels": PHASES,
                "values": [row["accuracy"] for row in tables["phase"]],
            },
            "correctness_per_reply": {
                "labels": turns,
                "series": [{"key": key, "name": label, "values": [int(v) for v in per_turn[key]]}
                           for key, label in CORRECTNESS.items()],
            },
            "response_time_trend": {
                "labels": [ts.strftime("%b %d %H:%M") for ts in trend["timestamp"]],
                "values": [_round(v, 2) for v in trend["response_time"]],
            },
            "rating_distribution": {
                "labels": [item["label"] for item in tables["rating"]],
                "values": [item["count"] for item in tables["rating"]],
            },
            "length_preference": {
                "labels": [item["label"] for item in tables["length"]],
                "values": [item["count"] for item in tables["length"]],
            },
        }

    # ============ FR21: INSIGHTS ============

    @staticmethod
    def _insights(topic_table, best, worst, phase_table, correctness, response_times, length_dist):
        insights = []
        if best:
            insights.append(f"Strongest topic: {best['topic']} with {best['accuracy']}% accuracy "
                            f"over {_replies(best['rated'], 'rated ')}.")
        if worst:
            insights.append(f"Weakest topic: {worst['topic']} with {worst['accuracy']}% accuracy "
                            f"over {_replies(worst['rated'], 'rated ')}.")

        start, end = phase_table[0]["accuracy"], phase_table[-1]["accuracy"]
        if start is not None and end is not None:
            change = round(end - start, 1)
            trend = "rises" if change > 0 else "drops" if change < 0 else "stays level"
            insights.append(f"Accuracy {trend} from {start}% in the start phase to {end}% in the end phase.")

        timed_topics = [row for row in topic_table if row["avg_response_time"] is not None]
        if response_times["count"] and timed_topics:
            slowest = max(timed_topics, key=lambda row: row["avg_response_time"])
            insights.append(f"Average response time is {response_times['mean']} s; "
                            f"{slowest['topic']} replies are the slowest at {slowest['avg_response_time']} s.")

        top_length = max(length_dist, key=lambda item: item["count"])
        if top_length["count"]:
            insights.append(f"Most replies were judged \"{top_length['label']}\" ({top_length['percent']}%).")

        general = next((row for row in topic_table if row["topic"] == GENERAL), None)
        if general and general["subjects"]:
            insights.append(f"Outside the five AI domains, questions were about: {', '.join(general['subjects'])}.")

        if correctness["unrated"]:
            insights.append(f"{_replies(correctness['unrated'])} without feedback "
                            f"{'is' if correctness['unrated'] == 1 else 'are'} left out of accuracy.")
        return insights

    # ============ DASHBOARD ============

    def compute_metrics(self, df):
        """Metrics, tables and insights for a set of replies"""
        if df.empty:
            return {"empty": True}

        topic_table = self._group_table(df, "topic", ALL_TOPICS)
        best, worst = self._strongest_and_weakest(topic_table)
        several_rated = sum(row["accuracy"] is not None for row in topic_table) > 1
        for row in topic_table:
            # The most asked-about subjects in each domain, e.g. General: Literacy Rate
            row["subjects"] = df.loc[df["topic"] == row["topic"], "subject"].value_counts().index[:SUBJECTS_PER_TOPIC].tolist()
            # Strongest / weakest marks on the topic cards need at least two rated topics to compare.
            row["flag"] = ("best" if row is best else "weak" if row is worst else None) if several_rated else None
        phase_table = self._group_table(df, "phase", PHASES, keep_empty=True)
        overall = self._summaries(df, pd.Series("all", index=df.index))["all"]
        correctness = self._correctness_summary(overall)
        response_times = self._response_time_summary(df)
        rating_dist = self._distribution(df["rating"], RATINGS)
        length_dist = self._distribution(df["length_type"], LENGTH_TYPES)

        return {
            "empty": False,
            "kpis": {
                "sessions": int(df["session_id"].nunique()),
                "replies": overall["replies"],
                "rated": overall["rated"],
                "accuracy": overall["accuracy"],
                "correct_pct": correctness["correct_pct"],
                "avg_rating": overall["avg_rating"],
                "avg_response_time": response_times["mean"],
            },
            "correctness": correctness,
            "tables": {
                "topic": topic_table,
                "phase": phase_table,
                "response_time": response_times,
                "rating": rating_dist,
                "length": length_dist,
            },
            "insights": self._insights(topic_table, best, worst, phase_table, correctness, response_times, length_dist),
        }

    def build_dashboard(self, user_id, session_id=None, theme="light"):
        """Dashboard data for all of a user's sessions, or for one session"""
        df = self.load_replies(user_id)
        sessions = [] if df.empty else self.session_table(
            df, self.db.get_ended_sessions(user_id), self.db.get_session_titles(user_id))

        # A chat without replies yet (e.g. a new chat) shows all sessions instead.
        session = next((row for row in sessions if row["session_id"] == session_id), None)
        scope = {"session_id": None, "title": "All sessions"}
        if session:
            df = df[df["session_id"] == session_id]
            scope = {key: session[key] for key in ("session_id", "title", "status", "ended_at")}

        colors = topic_colors(ALL_TOPICS, theme)
        metrics = self.compute_metrics(df)
        if not metrics["empty"]:
            metrics["tables"]["replies"] = self._reply_table(df)
            metrics["charts"] = build_figures(self._chart_data(df, metrics["tables"]), colors, theme)
            metrics["chart_template"] = TEMPLATE
        return {
            "scope": scope,
            "topics": ALL_TOPICS,
            # Same colour per topic as in the graphs, for the topic-based performance cards
            "topic_colors": colors,
            "sessions": sessions,
            **metrics,
        }

    # ============ FR22: SESSION TERMINATION ============

    def build_session_summary(self, user_id, session_id):
        """Final analytics summary of one session, ready to be stored permanently"""
        df = self.load_replies(user_id, session_id)
        if df.empty:
            return None
        metrics = self.compute_metrics(df)
        return {
            "user_id": user_id,
            "session_id": session_id,
            "title": self.db.get_session_title(user_id, session_id)
                     or fallback_title(self._first_questions(df).get(session_id, "")),
            "started_at": df["timestamp"].min().to_pydatetime(),
            "ended_at": datetime.now(),
            "kpis": metrics["kpis"],
            "correctness": metrics["correctness"],
            "topic_table": metrics["tables"]["topic"],
            "phase_table": metrics["tables"]["phase"],
            "response_time": metrics["tables"]["response_time"],
            "rating_distribution": metrics["tables"]["rating"],
            "length_preference": metrics["tables"]["length"],
            "insights": metrics["insights"],
        }
