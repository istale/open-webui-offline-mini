#!/usr/bin/env python3
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_text_image(
    text, width=800, height=600, bg_color=(255, 255, 255), text_color=(0, 0, 0)
):
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()

    lines = text.split("\n")
    y = 50
    line_height = 30

    for line in lines:
        draw.text((50, y), line, fill=text_color, font=font)
        y += line_height

    return img


def generate_demo_data():
    root = Path.cwd()

    deck_dir = root / "domain_knowledge_materials" / "demo_ml_basics"
    slides_dir = deck_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    exam_dir = root / "domain_knowledge_exams" / "demo_ml_exam"
    questions_dir = exam_dir / "questions"
    answers_dir = exam_dir / "answers"
    questions_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    slide_contents = [
        (
            "slide_0001",
            "Introduction to Machine Learning\n\n- Definition: Algorithms that learn from data\n- Types: Supervised, Unsupervised, Reinforcement\n- Applications: Image recognition, NLP, Recommendation",
            "ML Overview",
        ),
        (
            "slide_0002",
            "Supervised Learning\n\n- Training data has labels\n- Goal: Learn mapping from input to output\n- Examples: Classification, Regression\n- Common algorithms: Linear Regression, Decision Trees",
            "Supervised Learning",
        ),
        (
            "slide_0003",
            "Unsupervised Learning\n\n- Training data has no labels\n- Goal: Find hidden patterns\n- Examples: Clustering, Dimensionality Reduction\n- Common algorithms: K-Means, PCA",
            "Unsupervised Learning",
        ),
        (
            "slide_0004",
            "Training vs Testing\n\n- Split data into train/test sets\n- Train on training data\n- Evaluate on unseen test data\n- Avoid overfitting to training data",
            "Train Test Split",
        ),
        (
            "slide_0005",
            "Overfitting and Underfitting\n\n- Overfitting: Model memorizes training data\n- Underfitting: Model too simple\n- Solutions: Cross-validation, Regularization\n- Bias-Variance Tradeoff",
            "Model Generalization",
        ),
        (
            "slide_0006",
            "Feature Engineering\n\n- Select relevant features\n- Transform raw data\n- Normalization and Scaling\n- Handle missing values",
            "Feature Engineering",
        ),
        (
            "slide_0007",
            "Model Evaluation Metrics\n\n- Classification: Accuracy, Precision, Recall, F1\n- Regression: MSE, RMSE, MAE, R-squared\n- Confusion Matrix\n- ROC Curve and AUC",
            "Evaluation Metrics",
        ),
        (
            "slide_0008",
            "Cross-Validation\n\n- K-Fold Cross Validation\n- Reduces variance in evaluation\n- Better use of limited data\n- Stratified sampling for imbalanced data",
            "Cross Validation",
        ),
        (
            "slide_0009",
            "Neural Networks Basics\n\n- Inspired by biological neurons\n- Layers: Input, Hidden, Output\n- Weights and biases\n- Activation functions: ReLU, Sigmoid, Tanh",
            "Neural Networks",
        ),
        (
            "slide_0010",
            "Deep Learning Overview\n\n- Deep neural networks\n- Requires large datasets\n- GPU acceleration\n- Frameworks: TensorFlow, PyTorch",
            "Deep Learning",
        ),
    ]

    print("Generating slides...")
    for slide_id, text, concept in slide_contents:
        img = create_text_image(text)
        img_path = slides_dir / f"{slide_id}.png"
        img.save(img_path)

        txt_path = slides_dir / f"{slide_id}.txt"
        txt_path.write_text(text, encoding="utf-8")

        print(f"  Created: {img_path}")

    meta = {
        "title": "Machine Learning Basics",
        "tags": ["ML", "AI", "intro"],
        "created_at": "2026-02-16",
        "notes": "Demo deck for KLS testing",
    }
    (deck_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    question_contents = [
        (
            "q_0001",
            "What is the main characteristic of supervised learning?\n\nA) No labels in training data\nB) Training data has labels\nC) Uses only neural networks\nD) No training phase required",
            "B",
        ),
        (
            "q_0002",
            "Which algorithm is commonly used for clustering?\n\nA) Linear Regression\nB) Decision Trees\nC) K-Means\nD) Logistic Regression",
            "C",
        ),
        (
            "q_0003",
            "What problem occurs when a model memorizes training data?\n\nA) Underfitting\nB) Overfitting\nC) Normal fitting\nD) Bias reduction",
            "B",
        ),
        (
            "q_0004",
            "What does MSE stand for in regression evaluation?\n\nA) Mean Slope Error\nB) Mean Square Error\nC) Model Selection Error\nD) Maximum Square Estimation",
            "B",
        ),
        (
            "q_0005",
            "Which activation function is commonly used in hidden layers?\n\nA) Sigmoid only\nB) ReLU\nC) Step function\nD) No activation function",
            "B",
        ),
        (
            "q_0006",
            "What is the purpose of cross-validation?\n\nA) Increase training time\nB) Reduce evaluation variance\nC) Add more features\nD) Remove all outliers",
            "B",
        ),
        (
            "q_0007",
            "What should be done with missing values in feature engineering?\n\nA) Always delete the entire row\nB) Ignore them completely\nC) Handle them appropriately\nD) Replace with random numbers",
            "C",
        ),
        (
            "q_0008",
            "What does PCA stand for?\n\nA) Principal Component Analysis\nB) Partial Classification Algorithm\nC) Predictive Clustering Approach\nD) Primary Component Aggregation",
            "A",
        ),
        (
            "q_0009",
            "Which metric combines precision and recall?\n\nA) Accuracy\nB) F1 Score\nC) ROC\nD) MSE",
            "B",
        ),
        (
            "q_0010",
            "What hardware is commonly used to accelerate deep learning?\n\nA) CPU only\nB) GPU\nC) RAM\nD) Hard drive",
            "B",
        ),
    ]

    print("\nGenerating questions...")
    answer_key = {}
    for q_id, text, answer in question_contents:
        img = create_text_image(text, height=400)
        img_path = questions_dir / f"{q_id}.png"
        img.save(img_path)

        txt_path = questions_dir / f"{q_id}.txt"
        txt_path.write_text(text, encoding="utf-8")

        answer_key[q_id] = {"answer": answer}

        print(f"  Created: {img_path}")

    (answers_dir / "answer_key.json").write_text(
        json.dumps(answer_key, indent=2), encoding="utf-8"
    )

    exam_meta = {
        "title": "ML Basics Exam",
        "tags": ["test", "ml", "demo"],
        "created_at": "2026-02-16",
        "notes": "Demo exam for KLS testing",
    }
    (exam_dir / "meta.json").write_text(
        json.dumps(exam_meta, indent=2), encoding="utf-8"
    )

    print("\nDemo data generation complete!")
    print(f"  Deck: {deck_dir}")
    print(f"  Exam: {exam_dir}")
    print(f"  Answer key: {answers_dir / 'answer_key.json'}")


if __name__ == "__main__":
    generate_demo_data()
