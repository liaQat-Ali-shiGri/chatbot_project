"""Topic classification for chat messages (FR15).

A hybrid classifier:
1. Keyword rules give a high-precision label when a message names its domain.
2. A TF-IDF + Logistic Regression model (scikit-learn), trained on a small
   seed corpus, labels messages that describe a domain without its keywords.
3. Short follow-ups with no topical signal ("explain that again", "give an
   example") inherit the previous topic of the session, so a multi-turn
   conversation stays in the right domain.
Generic wording such as "AI" is ignored by the model, because every domain is
an AI domain: "What is AI?" is General, not Healthcare AI. Questions outside
the five domains (e.g. literacy rates) are General; their specific subject is
named separately by chat_titles.py.
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

TOPICS = ["Machine Learning", "Deep Learning", "Healthcare AI", "Power Systems", "E-commerce AI"]
GENERAL = "General"

KEYWORDS = {
    "Machine Learning": (
        "machine learning", "supervised", "unsupervised", "regression", "classifier",
        "clustering", "decision tree", "random forest", "svm", "k-means", "knn",
        "overfitting", "underfitting", "feature engineering", "scikit-learn", "sklearn",
        "gradient boosting", "gradient descent", "xgboost", "cross-validation",
        "naive bayes", "bias-variance", "reinforcement learning", "feature scaling",
        "hyperparameter", "training data", "dimensionality reduction", "pca",
    ),
    "Deep Learning": (
        "deep learning", "deep model", "neural network", "cnn", "rnn", "lstm", "gpu",
        "backpropagation", "convolutional", "attention mechanism", "pytorch", "tensorflow",
        "keras", "autoencoder", "activation function", "dropout", "large language model",
        "llm", "gpt", "bert", "fine-tuning", "embedding layer",
    ),
    "Healthcare AI": (
        "healthcare", "health", "medical", "diagnosis", "hospital", "patient", "disease",
        "clinical", "radiology", "drug discovery", "medicine", "ehr", "cancer", "x-ray",
        "mri", "tumor", "diabetes", "symptom", "doctor",
    ),
    "Power Systems": (
        "power system", "electricity", "electric", "electrical", "power grid", "smart grid",
        "renewable", "solar", "wind turbine", "wind farm", "wind energy", "wind power",
        "load forecasting", "voltage", "power plant", "power generation", "transmission line",
        "substation", "power outage", "energy storage", "power flow",
    ),
    "E-commerce AI": (
        "e-commerce", "ecommerce", "recommendation system", "recommender", "shopping",
        "retail", "online store", "shopping cart", "customer churn", "dynamic pricing",
        "product recommendation", "inventory", "customer", "online shop", "marketplace",
        "checkout", "buy", "buying", "purchase",
    ),
}

SEED_EXAMPLES = {
    "Machine Learning": [
        "what is the difference between supervised and unsupervised learning",
        "how does linear regression fit a line to data",
        "explain logistic regression for binary classification",
        "how do I avoid overfitting my model",
        "what is a decision tree and how does it split",
        "how does k-means clustering group data points",
        "explain the bias variance tradeoff",
        "how do I choose features for a predictive model",
        "what is cross validation used for",
        "compare random forest and gradient boosting",
        "how to evaluate a model with precision and recall",
        "how does gradient descent minimize the loss function",
        "what is a training set and a test set",
    ],
    "Deep Learning": [
        "how does a neural network learn its weights",
        "explain backpropagation step by step",
        "what is a convolutional layer in image recognition",
        "how do transformers use self attention",
        "what is the vanishing gradient problem",
        "difference between rnn and lstm for sequences",
        "what activation function should hidden layers use",
        "how does dropout prevent overfitting in deep networks",
        "how are large language models trained",
        "what is transfer learning with pretrained models",
        "how do generative adversarial networks work",
        "what does batch normalization do",
    ],
    "Healthcare AI": [
        "how is ai used to diagnose diseases from medical images",
        "can machine learning predict patient readmission",
        "ai for detecting cancer in radiology scans",
        "how do hospitals use predictive analytics",
        "what are the privacy concerns with patient health records",
        "ai in drug discovery and clinical trials",
        "predicting diabetes risk from patient data",
        "how accurate is ai at reading x-rays",
        "using wearables to monitor heart rate and health",
        "ai chatbots for medical symptom checking",
        "early detection of alzheimer disease with ai",
        "how can ai help doctors in treatment planning",
    ],
    "Power Systems": [
        "how does ai forecast electricity demand",
        "what is a smart grid",
        "how to integrate solar and wind energy into the grid",
        "predicting power outages with machine learning",
        "how is voltage stability maintained in a power network",
        "optimizing energy storage and battery dispatch",
        "fault detection in transmission lines",
        "how does load balancing work in electrical grids",
        "predictive maintenance for power plant equipment",
        "what is economic dispatch in power generation",
        "forecasting renewable energy generation from weather",
        "how do utilities reduce peak load",
    ],
    "E-commerce AI": [
        "how do online stores recommend products to customers",
        "how does amazon recommendation engine work",
        "predicting customer churn for an online shop",
        "dynamic pricing strategies using ai",
        "how to personalize the shopping experience",
        "detecting fraudulent transactions in online payments",
        "forecasting product demand for inventory planning",
        "customer segmentation for marketing campaigns",
        "how do chatbots help customer service in retail",
        "analyzing product reviews with sentiment analysis",
        "reducing cart abandonment on a website",
        "visual search for finding similar products",
        "how do websites suggest items users might like",
        "which items should we show to returning buyers",
    ],
    GENERAL: [
        "hello", "hi there", "good morning", "thank you", "thanks a lot", "bye",
        "how are you", "who are you", "what is your name",
        "tell me a joke", "what time is it", "recommend a good movie",
        "how do I cook pasta", "write a poem about the sea",
        "who won the football match", "translate hello into spanish",
        # Everyday knowledge outside the five AI domains
        "what is the unemployment rate in europe", "what is the gdp of china",
        "how many people live in india", "which countries have the highest education levels",
        "who is the president of the united states", "how tall is mount everest",
        "explain photosynthesis", "what caused the first world war", "who invented the computer",
        "how do I learn english quickly", "what is the meaning of life",
        "what is the future of technology", "is it safe for humanity", "tell me about ancient rome",
        "what are the rules of football", "how do vaccines work for children in schools",
        "what is climate change", "who painted the mona lisa", "how does the stock market work",
    ],
}

# Generic AI wording ("AI", "artificial intelligence") appears in every domain of this project,
# so it is removed before the model looks at the text and cannot pull a question into one domain.
GENERIC_AI = re.compile(r"\b(?:ai|a\.i\.|artificial\s+intell?[ei]gen[cs]e|artificial|intell?[ei]gen[cs]e)\b")


def domain_text(text):
    return " ".join(GENERIC_AI.sub(" ", str(text or "").lower()).split())

# Below this probability the model is treated as unsure of the topic.
CONFIDENCE_THRESHOLD = 0.35
FOLLOW_UP_MAX_WORDS = 12
# Words that refer back to the previous turn rather than start a new topic.
FOLLOW_UP_CUES = re.compile(
    r"\b(it|its|this|that|these|those|they|them|their|above|previous|same|another|"
    r"more|again|further|example|examples|elaborate|explain|simpler|detail|details|"
    r"why|also|else|continue|compare|difference|first|second|last|what about)\b"
)


def is_follow_up(text):
    """A short message that refers back to the previous turn, e.g. "give me an example\""""
    text = str(text or "").lower()
    return len(text.split()) <= FOLLOW_UP_MAX_WORDS and bool(FOLLOW_UP_CUES.search(text))


def _keyword_pattern(keyword):
    # Allow a plural suffix so "CNNs" or "patients" still match.
    return re.compile(r"(?<![\w-])" + re.escape(keyword) + r"(?:s|es)?(?![\w-])")


class TopicClassifier:
    def __init__(self):
        self.patterns = {
            topic: [_keyword_pattern(keyword) for keyword in keywords]
            for topic, keywords in KEYWORDS.items()
        }
        texts, labels = [], []
        for topic, examples in SEED_EXAMPLES.items():
            texts.extend(examples)
            labels.extend([topic] * len(examples))
        self.model = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, preprocessor=domain_text),
            LogisticRegression(max_iter=1000, C=10),
        )
        self.model.fit(texts, labels)

    def _keyword_scores(self, text):
        return {
            topic: sum(1 for pattern in patterns if pattern.search(text))
            for topic, patterns in self.patterns.items()
        }

    def classify(self, message, previous_topic=None):
        """Return one of TOPICS or GENERAL for a user message."""
        text = " ".join(str(message or "").lower().split())
        if not text:
            return previous_topic or GENERAL

        probabilities = dict(zip(self.model.classes_, self.model.predict_proba([text])[0]))

        scores = self._keyword_scores(text)
        best_score = max(scores.values())
        if best_score > 0:
            # Several domains named equally often: let the model break the tie.
            tied = [topic for topic, score in scores.items() if score == best_score]
            return max(tied, key=lambda topic: probabilities.get(topic, 0))

        if previous_topic in TOPICS and is_follow_up(text):
            return previous_topic

        predicted = max(probabilities, key=probabilities.get)
        if predicted != GENERAL and probabilities[predicted] >= CONFIDENCE_THRESHOLD:
            return predicted
        return GENERAL


classifier = TopicClassifier()
