from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "job_posts.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
VECTORIZER_PATH = BASE_DIR / "vectorizer.pkl"


def train_and_save() -> None:
    data = pd.read_csv(DATA_PATH)
    data["text"] = data["title"].fillna("") + " " + data["description"].fillna("")

    x_data = data["text"]
    y_data = data["label"]

    vectorizer = TfidfVectorizer(stop_words="english")
    x_vec = vectorizer.fit_transform(x_data)

    x_train, x_test, y_train, y_test = train_test_split(
        x_vec, y_data, test_size=0.2, random_state=42
    )

    model = MultinomialNB()
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Model accuracy: {accuracy:.2%}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    print(f"Saved model to: {MODEL_PATH}")
    print(f"Saved vectorizer to: {VECTORIZER_PATH}")


if __name__ == "__main__":
    train_and_save()
