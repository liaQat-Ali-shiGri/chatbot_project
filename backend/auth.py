from functools import wraps
from flask import request, jsonify, session

import os

# Mock user storage (in real project, store in MongoDB)
users = {}

def mock_login(email, name):
    """Simple login for Phase 1"""
    session['user_id'] = email
    session['user_name'] = name
    session['logged_in'] = True
    return True

def logout():
    session.clear()
    return True

def is_logged_in():
    return session.get('logged_in', False)

def get_current_user():
    if is_logged_in():
        return {
            'user_id': session.get('user_id'),
            'user_name': session.get('user_name')
        }
    return None