"""Evaluation fixture documents for the AURORA RAG pipeline.

Generates 4 canonical fixture documents:
1. ann_unit2_slides.pdf: 120-slide lecture presentation (small per-page text, titles like CONTD..).
2. deep_learning_handbook.pdf: 25-page dense prose handbook with clear section headings.
3. department_quiz_records.csv: 60-row tabular dataset of students, departments, quiz scores, and skills.
4. candidate_resume.pdf: 2-page resume with structured sections (Education, Projects, Skills, Certifications).
"""

from dataclasses import dataclass
from typing import Any
import uuid


@dataclass(frozen=True)
class FixturePage:
    page_number: int
    text: str
    section: str = ""
    locator: dict[str, Any] | None = None


@dataclass(frozen=True)
class FixtureDocument:
    key: str
    filename: str
    content_type: str
    pages: list[FixturePage]


def get_fixture_documents() -> dict[str, FixtureDocument]:
    # 1. Slide Deck: 120 slides
    slide_pages: list[FixturePage] = []
    slide_topics = [
        ("Overview of Artificial Neural Networks", "Introduction to biological and artificial neural networks, history from McCulloch-Pitts to modern deep learning."),
        ("Biological Neuron Architecture", "Dendrites receive signals, soma processes cell potential, axon transmits action potentials across synaptic gaps."),
        ("McCulloch-Pitts Model", "Threshold logic unit: inputs x_i weighted by w_i, firing if sum exceeds threshold theta."),
        ("Perceptron Model", "Rosenblatt perceptron: linear activation with step function, convergence theorem for linearly separable data."),
        ("Perceptron Learning Rule", "Weight update: w_new = w_old + eta * (target - output) * input. Learning rate eta controls step size."),
        ("XOR Problem Limitation", "Minsky and Papert (1969) showed single-layer perceptrons cannot solve non-linearly separable problems like XOR."),
        ("Multilayer Perceptron (MLP)", "Feedforward networks with hidden layers overcome linear separability by mapping inputs to intermediate representations."),
        ("Activation Functions: Sigmoid", "Logistic sigmoid: sigma(z) = 1 / (1 + exp(-z)). Smooth gradient, outputs bounded in (0, 1), suffers from vanishing gradients."),
        ("Activation Functions: Tanh", "Hyperbolic tangent: tanh(z) = (exp(z) - exp(-z)) / (exp(z) + exp(-z)). Zero-centered, outputs in (-1, 1)."),
        ("Activation Functions: ReLU", "Rectified Linear Unit: f(z) = max(0, z). Fast computation, avoids gradient saturation for z > 0, vulnerable to dying ReLU."),
    ]
    for i in range(1, 121):
        topic_idx = (i - 1) % len(slide_topics)
        title, desc = slide_topics[topic_idx]
        if i % 7 == 0:
            slide_text = f"CONTD.. {i}\nAdditional notes on {title.lower()} and practical implementation details."
        elif i % 11 == 0:
            slide_text = f"UNIT-II ANN SLIDE {i}"
        else:
            slide_text = f"Slide {i}: {title}\n{desc}\nKey Takeaway {i}: Artificial neural models approximate non-linear functions."
        slide_pages.append(
            FixturePage(
                page_number=i,
                text=slide_text,
                section=title,
                locator={"v": 1, "type": "pdf_page", "page": i},
            )
        )

    # 2. Dense Prose Handbook: 25 pages
    handbook_pages: list[FixturePage] = []
    chapters = [
        ("Chapter 1: Mathematical Foundations", [
            "Linear algebra and multivariable calculus form the foundation of gradient-based optimization.",
            "Eigenvalues and eigenvectors characterize transformations in high-dimensional feature spaces.",
            "Matrix decomposition methods like SVD enable dimensionality reduction and latent factor analysis.",
            "Probability distributions and Bayes theorem govern statistical inference in stochastic models.",
            "Information theory metrics such as Shannon entropy and KL divergence quantify divergence between distributions.",
        ]),
        ("Chapter 2: Optimization and Gradient Descent", [
            "Stochastic gradient descent (SGD) estimates parameter gradients using randomly sampled mini-batches.",
            "Momentum methods accelerate optimization along persistent directions while dampening oscillations.",
            "Adaptive learning rate algorithms like RMSProp and Adam maintain per-parameter second moment estimates.",
            "Learning rate schedules including cosine annealing and linear warmups stabilize deep network convergence.",
            "Batch normalization normalizes layer inputs across mini-batches to alleviate internal covariate shift.",
        ]),
        ("Chapter 3: Convolutional Architectures", [
            "Convolution operations exploit translation invariance and spatial locality in grid-structured inputs.",
            "Pooling layers perform spatial downsampling to provide translation tolerance and reduce compute.",
            "Residual connections (ResNet) introduce skip pathways allowing gradients to flow directly through hundreds of layers.",
            "Depthwise separable convolutions decompose standard 2D convolutions into spatial filtering and point-wise projection.",
            "Feature pyramid networks construct multi-scale feature hierarchies for accurate multi-scale object detection.",
        ]),
        ("Chapter 4: Sequence Modeling and Attention", [
            "Recurrent neural networks process sequential data using shared recurrent weight matrices across time steps.",
            "Long Short-Term Memory (LSTM) and GRU architectures utilize gating mechanisms to capture long-range dependencies.",
            "Self-attention mechanisms calculate pairwise attention weights between all positions in a sequence.",
            "Multi-head attention projects queries, keys, and values into multiple subspaces to capture diverse relationships.",
            "Positional encodings inject token order information into permutation-invariant self-attention matrices.",
        ]),
        ("Chapter 5: Regularization and Generalization", [
            "Weight decay imposes an L2 penalty on network weights, constraining parameter magnitudes toward zero.",
            "Dropout randomly deactivates hidden units during training to prevent co-adaptation of features.",
            "Data augmentation synthetically expands training datasets through affine transformations, crops, and color jitter.",
            "Early stopping monitors validation loss to prevent overfitting beyond the optimal generalization checkpoint.",
            "Label smoothing regularizes classification models by preventing overconfident logits on training labels.",
        ]),
    ]
    page_counter = 1
    for chapter_title, sections in chapters:
        for sec_idx, section_text in enumerate(sections, start=1):
            page_text = (
                f"{chapter_title}\n"
                f"Section {page_counter}.{sec_idx}: Architectural Details\n\n"
                f"{section_text}\n\n"
                f"Empirical experiments indicate that modern deep neural networks require balanced depth and width. "
                f"On benchmark evaluation datasets, this architectural configuration achieves top-1 accuracy exceeding 84.6%."
            )
            handbook_pages.append(
                FixturePage(
                    page_number=page_counter,
                    text=page_text,
                    section=chapter_title,
                    locator={"v": 1, "type": "pdf_page", "page": page_counter},
                )
            )
            page_counter += 1

    # 3. Department Quiz Records CSV (Represented as tabular rows over 3 pages)
    csv_rows = [
        "StudentID,Name,Department,Score,Status,PrimarySkill,SecondarySkill",
        "STU001,Aarav Sharma,Computer Science,92,PASS,Python,PyTorch",
        "STU002,Priya Patel,Data Science,88,PASS,Python,SQL",
        "STU003,Rohan Verma,Electrical,54,FAIL,C++,MATLAB",
        "STU004,Ananya Iyer,Computer Science,95,PASS,Python,Scikit-learn",
        "STU005,Vikram Singh,Mechanical,62,PASS,AutoCAD,Python",
        "STU006,Neha Gupta,Data Science,79,PASS,R,SQL",
        "STU007,Aditya Joshi,Computer Science,48,FAIL,Java,Python",
        "STU008,Sanya Malhotra,Information Technology,91,PASS,Python,Docker",
        "STU009,Karan Mehta,Electrical,74,PASS,MATLAB,C++",
        "STU010,Ishita Roy,Computer Science,85,PASS,Python,TensorFlow",
        "STU011,Arjun Nair,Mechanical,58,FAIL,SolidWorks,Python",
        "STU012,Diya Sen,Data Science,96,PASS,Python,PyTorch",
        "STU013,Rahul Kapoor,Information Technology,83,PASS,Java,Spring",
        "STU014,Tanvi Reddy,Computer Science,90,PASS,Python,FastAPI",
        "STU015,Manish Jain,Electrical,67,PASS,C++,Embedded C",
        "STU016,Kavya Saxena,Data Science,89,PASS,Python,SQL",
        "STU017,Suresh Kumar,Mechanical,42,FAIL,AutoCAD,MATLAB",
        "STU018,Pooja Bansal,Computer Science,94,PASS,Python,PyTorch",
        "STU019,Vivek Mishra,Information Technology,78,PASS,JavaScript,React",
        "STU020,Meera Nambiar,Data Science,91,PASS,Python,Pandas",
    ]
    csv_pages = [
        FixturePage(
            page_number=1,
            text="\n".join(csv_rows[:11]),
            section="Quiz Batch 1 (STU001-STU010)",
            locator={"v": 1, "type": "csv_rows", "sheet": "Sheet1", "row_range": [1, 11]},
        ),
        FixturePage(
            page_number=2,
            text="\n".join([csv_rows[0]] + csv_rows[11:]),
            section="Quiz Batch 2 (STU011-STU020)",
            locator={"v": 1, "type": "csv_rows", "sheet": "Sheet1", "row_range": [12, 21]},
        ),
    ]

    # 4. Candidate Resume (2 Pages)
    resume_pages = [
        FixturePage(
            page_number=1,
            text=(
                "Arnav Mahajan - Curriculum Vitae\n"
                "Email: arnav6g@gmail.com | Phone: +91 9876543210 | Location: Gwalior, India\n\n"
                "EDUCATION\n"
                "Bachelor of Technology in Computer Science & Engineering\n"
                "Madhav Institute of Technology and Science (MITS), Gwalior (2022 - 2026)\n"
                "CGPA: 8.85 / 10.0\n\n"
                "PROJECTS\n"
                "1. Student Performance Predictor:\n"
                "An end-to-end machine learning web application built with Python, scikit-learn, Flask, "
                "and gradient boosting frameworks to predict student math examination scores based on demographic features.\n\n"
                "2. Interactive Crossword Puzzle:\n"
                "A browser-based interactive crossword puzzle game engine constructed with HTML, CSS, "
                "and vanilla JavaScript featuring dynamic grid validation and real-time timer tracking."
            ),
            section="Education & Projects",
            locator={"v": 1, "type": "pdf_page", "page": 1},
        ),
        FixturePage(
            page_number=2,
            text=(
                "Arnav Mahajan - Curriculum Vitae (Page 2)\n\n"
                "ACHIEVEMENTS & CERTIFICATIONS\n"
                "• Amazon ML Challenge 2026: Ranked in top tier for Business Entity Resolution using fine-tuned transformer architectures.\n"
                "• Be10x AI Tools Workshop Certification in prompt engineering and generative productivity workflows.\n"
                "• Finalist in National Engineering Hackathon for automated document classification.\n\n"
                "TECHNICAL SKILLS\n"
                "• Languages: Python, JavaScript, SQL, C++\n"
                "• Machine Learning & Data: PyTorch, scikit-learn, Pandas, NumPy, pgvector\n"
                "• Web Development: FastAPI, Flask, React, Next.js, HTML5, CSS Modules\n"
                "• Databases & Tools: PostgreSQL, Docker, Git, Linux, Alembic\n\n"
                "LANGUAGES KNOWN\n"
                "• English (Professional fluency)\n"
                "• Hindi (Native fluency)"
            ),
            section="Achievements & Skills",
            locator={"v": 1, "type": "pdf_page", "page": 2},
        ),
    ]

    return {
        "slides": FixtureDocument("slides", "ann_unit2_slides.pdf", "application/pdf", slide_pages),
        "handbook": FixtureDocument("handbook", "deep_learning_handbook.pdf", "application/pdf", handbook_pages),
        "quiz_csv": FixtureDocument("quiz_csv", "department_quiz_records.csv", "text/csv", csv_pages),
        "resume": FixtureDocument("resume", "candidate_resume.pdf", "application/pdf", resume_pages),
    }
