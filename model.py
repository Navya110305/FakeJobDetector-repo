from pathlib import Path
import re

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "job_posts.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
VECTORIZER_PATH = BASE_DIR / "vectorizer.pkl"


def extract_features(text):
    """Extract additional features indicating fake jobs."""
    text_lower = text.lower()
    features = text
    
    # Strong fake job indicators with multiple patterns
    fake_indicators = [
        # Known fake company names
        (r'\b(cod(?:e)?soft|cognifyz|apex|quickhirepro|instantjobgate|earnmorenow)\b', "fake_company_name"),
        # Communication methods
        (r'\b(whatsapp|telegram|viber|signal|wechat)\b', "whatsapp_contact"),
        (r'\bonly\s+(whatsapp|telegram)\b', "messaging_only"),
        # Payment/fees
        (r'\b(registration\s+fee|joining\s+fee|application\s+fee)\b', "registration_fee"),
        (r'\b(payment|charge|deposit)\s+(required|mandatory|needed)\b', "payment_required"),
        (r'\brupe[es]{1,2}\b.*(?:pay|invest)', "payment_in_currency"),
        (r'\b(bitcoin|crypto|cryptocurrency)\b', "crypto_payment"),
        # Pressure tactics
        (r'\b(urgent|immediately|last\s+minute|asap)\b', "urgency_tactic"),
        (r'\blimited\s+(seats?|positions?|slots?)\b', "limited_seats"),
        (r'\b(fast|quick)\s+(hiring|recruitment|job)\b', "quick_hiring"),
        # Unrealistic promises
        (r'\b(guarantee|guaranteed|100%\s+placement)\b', "unrealistic_promise"),
        (r'\b(unlimited|high|easy)\s+(earning|income|money)\b', "unrealistic_earnings"),
        # General patterns
        (r'\b(work\s+from\s+home|wfh).{0,30}(investment|fee|payment)\b', "wfh_with_payment"),
        (r'\bno\s+(experience|qualification|education).{0,30}(required|needed)\b', "no_requirements"),
    ]
    
    for pattern, label in fake_indicators:
        if re.search(pattern, text_lower):
            features += f" FAKE_IND_{label} "
    
    # Strong genuine job indicators
    genuine_indicators = [
        # Official channels
        (r'\b(official|careers?\s+page|careers?\s+site)\b', "official_channel"),
        (r'\b(careers\.[a-z]+|jobs\.[a-z]+)\b', "career_domain"),
        (r'\b(linkedin\.com|indeed\.com|glassdoor|monster|naukri)\b', "job_platform"),
        # No payment
        (r'\b(no.*fee|free.{0,15}(application|apply))\b', "no_fees"),
        (r'\bno\s+(payment|charges?|investment)\b', "no_payment"),
        # Direct application
        (r'\b(apply\s+directly|send.*resume|send.*cv)\b', "direct_apply"),
        (r'\b(hr@|careers@|jobs@|recruiting@|contact@)\b', "official_email"),
        # Company info
        (r'\b(founded|established)\s+in\s+\d{4}\b', "company_founded"),
        (r'\b(employees?|staff|team).*(?:in|at|of)\b', "company_size"),
        (r'\b(headquarters?|office|location).*(?:in|at|,)\b', "company_location"),
    ]
    
    for pattern, label in genuine_indicators:
        if re.search(pattern, text_lower):
            features += f" GENUINE_IND_{label} "
    
    return features


def train_and_save() -> None:
    data = pd.read_csv(DATA_PATH)
    data["url"] = data.get("url", "").fillna("")
    data["text"] = (
        data["title"].fillna("")
        + " "
        + data["description"].fillna("")
        + " "
        + data["url"].fillna("")
    )
    
    # Apply feature extraction on combined text + URL
    data["text"] = data["text"].apply(extract_features)

    x_data = data["text"]
    y_data = data["label"]

    # Improved vectorizer with better parameters
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),  # Include bigrams
        min_df=1,  # Allow single-occurrence terms
        max_df=1.0,  # No upper limit
        lowercase=True,
        max_features=500,  # Limit features for small dataset
    )
    x_vec = vectorizer.fit_transform(x_data)

    # Split with stratification to maintain class balance
    x_train, x_test, y_train, y_test = train_test_split(
        x_vec, y_data, test_size=0.2, random_state=42, stratify=y_data
    )

    # Naive Bayes model
    model = MultinomialNB(alpha=0.1)  # Lower alpha for better discrimination
    model.fit(x_train, y_train)

    # Make predictions
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions, zero_division=0)
    recall = recall_score(y_test, predictions, zero_division=0)
    f1 = f1_score(y_test, predictions, zero_division=0)
    
    print(f"Model accuracy: {accuracy:.2%}")
    print(f"Precision (detecting fakes): {precision:.2%}")
    print(f"Recall (catching fakes): {recall:.2%}")
    print(f"F1-Score: {f1:.2%}")
    
    # Training metrics
    train_predictions = model.predict(x_train)
    train_accuracy = accuracy_score(y_train, train_predictions)
    print(f"\nTraining accuracy: {train_accuracy:.2%}")
    
    # Show feature importance for fake class (class 1)
    print(f"\nTop indicators for FAKE jobs:")
    fake_probs = model.feature_log_prob_[1]
    top_indices = fake_probs.argsort()[-10:][::-1]
    feature_names = vectorizer.get_feature_names_out()
    for idx in top_indices:
        print(f"  - {feature_names[idx]}: {fake_probs[idx]:.4f}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    print(f"\nSaved model to: {MODEL_PATH}")
    print(f"Saved vectorizer to: {VECTORIZER_PATH}")


if __name__ == "__main__":
    train_and_save()
