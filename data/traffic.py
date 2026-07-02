"""
Simulated production traffic: base queries plus paraphrases (which SHOULD hit
the same cache entry) and distinct queries with overlapping words (which should
NOT).  Each query carries a ground-truth `intent` label — the threshold tuner
uses it to measure wrong-hit rate at different similarity thresholds.
"""

TRAFFIC = [
    # intent: python_def — 1 original + 3 paraphrases
    {"prompt": "What is Python programming language?", "intent": "python_def"},
    {"prompt": "Python programming language — what is it?", "intent": "python_def"},
    {"prompt": "Describe the Python programming language", "intent": "python_def"},
    {"prompt": "What is the Python language used for programming?", "intent": "python_def"},

    # intent: python_install — shares 'python' but different question
    {"prompt": "How do I install Python on Windows?", "intent": "python_install"},
    {"prompt": "Installing Python on a Windows machine", "intent": "python_install"},

    # intent: refund_policy
    {"prompt": "What is your refund policy for annual subscriptions?", "intent": "refund_policy"},
    {"prompt": "Refund policy for annual subscription plans?", "intent": "refund_policy"},
    {"prompt": "Can I get a refund on my annual subscription?", "intent": "refund_policy"},

    # intent: cancel_account — shares 'subscription/account' vocabulary
    {"prompt": "How do I cancel my subscription account?", "intent": "cancel_account"},

    # intent: api_rate_limits
    {"prompt": "What are the API rate limits?", "intent": "api_rate_limits"},
    {"prompt": "API rate limits — what are the maximums?", "intent": "api_rate_limits"},

    # intent: reset_password
    {"prompt": "How do I reset my password?", "intent": "reset_password"},
    {"prompt": "Resetting my account password", "intent": "reset_password"},

    # time-sensitive — should get a short TTL
    {"prompt": "What is the weather today in Paris?", "intent": "weather_now"},

    # creative — should not be cached at all
    {"prompt": "Write me a poem about the rain", "intent": "creative_poem"},
]
