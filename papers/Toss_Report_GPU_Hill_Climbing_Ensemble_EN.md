# Toss Report: GPU Hill Climbing Ensemble for Merlin Framework

**JUNGHWAN NA**\*, Seoul National University, Laboratory of Molecular Developmental Genetics
**SUNGHOON BYUN**\*\*, Soongsil University, Laboratory of Computer Vision

---

## Abstract

This report presents the 1st place solution for the "Toss NEXT ML CHALLENGE: Ad Click Prediction (CTR) Model Development Competition." The training dataset consists of approximately 10M rows with 119 columns including the 'clicked' target column. The competition evaluates CTR prediction model applicability in actual production environments using a composite metric of Average Precision and Weighted-Logloss.

The inference environment is isolated, loading model weights to test performance and evaluate both CTR prediction accuracy and production applicability. Our solution achieved 1st place on both Public and Private leaderboards, consisting of a Hill-Climbing ensemble of 36 models.

Although ensembles are rarely used in production environments, our solution demonstrates the possibility of deploying ensemble models in production by leveraging NVIDIA-Merlin, a CTR-specialized framework that performs most computations on GPU. In production environments with limited time and computing resources for test dataset inference, our solution enables "Large-Large Ensemble" on large-scale datasets through fast training and inference.

By fully utilizing GPU-accelerated production environment advantages with open-source libraries including NVTabular, RAPIDS cuDF, PyTorch, and TensorFlow, we reduced training and inference time by approximately **50x or more**. From a business perspective, this suggests sufficient benefits to replace existing recommendation system update and real-time pipeline cycles with the Merlin framework.

**Keywords**: Recommendation Systems → CTR Prediction

---

## 1. Introduction

CTR (Click-Through Rate) represents the probability that a user will click on a given item or advertisement. This directly leads to revenue generation for advertisers and service providers, where increasing CTR is directly linked to service provider revenue.

However, from a business perspective, revenue and user experience often don't align, requiring balance between revenue optimization (accurate eCPM) and good recommendation order (Rank). This is why the Toss NEXT ML CHALLENGE required a composite metric—the metric below evaluates probability accuracy and order quality multi-dimensionally, representing a practical approach to achieve both "good predictions" and "good rankings" simultaneously.

### Competition Metric

$$Score = 0.5 \times AP + 0.5 \times \frac{1}{1 + WLL}$$

Where:
- **AP (Average Precision)** = $\frac{1}{|P|} \times \sum P(k) \cdot rel(k)$
  - P(k): Precision at rank k
  - rel(k): Relevance at rank k (click=1, no click=0)
  - |P|: Total number of clicks

- **WLL (Weighted LogLoss)** = $-\frac{1}{2} \times [\frac{1}{n_1} \sum \log(p_i) + \frac{1}{n_0} \sum \log(1-p_i)]$
  - 50:50 weighting for click/no-click
  - n₁, n₀: Sample count for each class
  - pᵢ: Predicted probability

---

## 2. Complex Metric Optimization

### BCE with AUC Early Stopping, Temperature Scaling

When composite metrics include F1 or AUC, directly optimizing them is computationally intractable and non-differentiable. However, by optimizing a surrogate loss like Binary Cross Entropy (BCE) and then applying thresholds, statistically consistent estimates can be obtained [1]. Additionally, minimizing cross-entropy loss produces a classifier with a decision function that approximates the optimal Bayes classifier, ultimately maximizing AUC [2].

Based on this rationale, our solution trains with BCE while using AUC for early stopping, rather than directly optimizing the composite metric. This maximizes rank during training, optimizing recommendation order and user preference.

**Temperature scaling** is a simple post-processing technique that rescales logits by a scalar temperature T. This transformation preserves accuracy (doesn't change argmax), maintains AUC (preserves ranking), and significantly improves calibration [3]. While standard temperature scaling only divides logit Z by T, our solution uses two parameters (T and bias)—adjusting prediction variance with T while shifting the mean with bias, which is closer to a variant of Platt scaling (Restricted Platt Scaling).

This approach first increases rank during training, then maximizes final score through post-processing, with each stage individually optimizable using methods like Optuna.

---

## 3. NVIDIA Merlin Framework

NVIDIA Merlin is an end-to-end GPU-accelerated framework for recommendation systems, designed to perform the entire process from data processing to model training and inference on GPU. The introduction of Merlin Framework enabled large-scale ensemble models to have realistic production applicability.

### 3.1 Merlin Framework Components

**NVTabular (Data Preprocessing)**
- GPU-accelerated feature engineering library
- cuDF-based API similar to pandas
- Recommendation system-specialized operators: Categorify, Normalize, FillMissing
- Core acceleration component of our solution

**Merlin Models (Model Training)**
- TensorFlow/PyTorch-based recommendation model library
- Industry-standard models: Wide&Deep, DLRM, DCN

**HugeCTR (Large-scale CTR Specialized)**
- C++-based high-performance CTR model training framework
- Multi-node, Multi-GPU training optimization
- Excluded from our solution due to Docker image build requirements and competition environment constraints

**Merlin Systems (Production Deployment)**
- Triton Inference Server integration
- Real-time recommendation serving optimization

### 3.2 GPU Categorify: Revolutionary Parallel Processing

The limitations of existing CPU-based categorical encoding are clear. Python's LabelEncoder processes 10.7M rows sequentially, with bottlenecks from Python GIL (Global Interpreter Lock) multi-threading limitations and repeated pandas DataFrame memory copies.

NVTabular's GPU Categorify takes a fundamentally different approach. With GPU parallel processing architecture, when processing our competition's 10.7M row dataset, it operates with simultaneous processing like 10,700 blocks × 1,000 threads = 10,700,000. Each CUDA Core independently processes rows with O(1) time complexity through GPU Hash Table. This massive parallelism theoretically enables tens of thousands of times throughput improvement compared to single-thread processing [4].

### 3.3 Zero-Copy I/O: Maximizing Memory Efficiency

Data I/O is a major bottleneck in large-scale dataset processing.

**Pandas Pipeline**: Disk → OS Buffer → User Space → pandas → numpy → GPU (5 memory copies)

**NVTabular Pipeline**: Parquet (Arrow Format) → Memory Map → GPU DMA (Zero-copy: no memory copies)

Arrow format Parquet files are columnar format directly readable by GPU. Through Memory-mapped I/O and DMA (Direct Memory Access), data loads directly to GPU memory without intermediate serialization. This brings dramatic performance improvements especially for 10M-scale datasets.

---

## 4. Data Preprocessing

### 4.1 Sequence Processing

The competition dataset is tabular data with approximately 10M rows and 119 columns. Each feature is anonymized, with variable-length sequence columns existing as strings like [512, 24, 3, 46...], consisting of integers and commas representing sequential user behavior data.

Three main preprocessing challenges existed:
1. max_len=6590 resulted in very long integer arrays
2. Increased embedding difficulty due to variable length
3. Small vocabulary and lack of direct correlation between sequence columns and CTR

We converted sequence columns to integer lists and integrated with NVTabular. Through EDA analysis, we found:
- Cohen's d = 0.182 (negligible effect size, meaning sequence length has practically negligible relationship with CTR)
- Gini coefficient = 0.936 (extreme inequality—a few popular items monopolize most interactions)
- High self-loop rates (70%+ self-transitions indicate redundant information)

**Conclusion**: Long sequences are repetition of the same information, not more information. We used a truncation strategy to approximately 1000 length.

We adopted **Bi-GRU sequence embedding** with masking for variable lengths—96 dimensions each for forward and backward GRU (192 total), projected to 32-dimensional features. The projection approach filtered noise and created intentional information bottlenecks, contributing to performance improvement.

### 4.2 Stratified 10-fold CV

When interpreting the dataset as time series with Sunday validation (temporal split), CV-LB difference was smallest. However, additional experiments found that "LB improves as more Sunday is included in training."

This led to the conclusion that "matching Sunday patterns in test is key, and to match Sunday patterns, Sunday must be learned in training"—essentially a Domain Adaptation task.

We finalized **stratified 10-fold CV** where [day_of_week, clicked] values are evenly distributed across each fold, enabling maximum Sunday inclusion in training while allowing OOF ensemble and stable LB prediction.

### 4.3 Feature Engineering

In ML, feature engineering typically sets min_improvement thresholds. The "3-sigma rule" suggests adopting improvements exceeding 3 standard deviations for stability [6]. However, CTR tasks have sparse-interaction and signal/data ratio issues, and with large-scale data, individual feature influence becomes statistically weaker.

For example, with 5fold-CV of 0.353183 ± 0.000688, stable min_improvement would be approximately +0.002 (99% confidence). No features showed such improvement, and exponentially increasing computation for multiple-seed, 10fold wasn't feasible.

**Conclusion**: Focus on model architecture and parameter tuning that can be reliably validated, rather than difficult-to-verify and marginal feature engineering. Multi-model ensemble that can correct individual model predictions is key.

---

## 5. Our Solution: GPU-Hill Climbing Ensemble

### 5.1 GPU-Hill Climbing Ensemble

Hill climbing ensemble finds optimal weighted averages of multiple OOF models [7]. This method stably finds optimal combinations regardless of each model's seed count, is free from overfitting, and allows numerically confirming each model's influence.

Since each OOF model had 10M rows × 2 columns (prediction, target), we accelerated computation by calculating competition metric and hill climbing on GPU using cudf. Computing AP with scikit-learn is very slow, so GPU computation using cupy is recommended.

Hill climbing inherently isn't exhaustive search and can fall into local optima, so we used random restart/shotgun approach with multiple initialization searches. After building the basic pipeline with XGBoost, we could rapidly explore diverse models by only changing model structure in the same pipeline without feature engineering.

**Different model architectures showed more performance improvement than multiple seeds of one model.** Finally, 25 of 36 ensemble models had actual weights used. In hill-climbing, same model seeds have high correlation causing weight dispersion, so single-seed wide_deep had the highest measured influence.

### 5.2 Tree-based Models

**XGBoost Depthwise**
- Solved class imbalance using only scale_pos_weight without negative sampling
- Stage 1: Optuna search for scale_pos_weight only
- Stage 2: Full model parameter tuning
- Fast search with LR=0.1, num_boost_round=150, ~5 seconds/trial on RTX A6000
- Main training: LR ~0.007, early stopping=300, ~14x lower LR for stable convergence

**XGBoost Lossguide**
- Unlike Depthwise splitting same-depth nodes simultaneously, Lossguide prioritizes splitting leaf nodes with largest loss reduction (like LightGBM)
- Fast convergence and high accuracy, but can create unbalanced trees with relatively higher overfitting risk

**CatBoost**
- Compromised with 10fold training after scale_pos_weight and model structure search
- Extended early stopping to 200 to allow slight overfitting

### 5.3 Deep Learning Models

**PyTorch MLP**
- Simplest architecture serving as baseline for more complex model pipelines
- 100 epochs, 5-epoch warm-up, max_LR: 0.002, 50% reduce-on-plateau scheduler

**xDeepFM**
- CIN layer for explicit high-order feature interactions + DNN for implicit interactions
- CIN_layer_sizes = [128, 128]: 2-layer CIN explicitly learning up to 3rd-order interactions
- More efficient architecture as CIN provides self-regularization effect

**DCNv3**
- 2024 state-of-the-art CTR model
- All features embedded to same dimension (128), parallel paths through LCN-ECN-DNN
- Tri-BCE loss combining independent learning of LCN/ECN predicting labels directly with auxiliary loss

**Wide&Deep**
- BiGRU + attention with 192 dimensions encoding sequences
- Unlike embedding projection, directly includes sequence embedding in gradient for learning
- Truncated to 512 length for fast training, only 5 epochs with SWA for generalization
- Trained with Sunday single split for OOF, contributing ~25% weight in hill-climbing ensemble as single seed

---

## 6. Accelerating Inference With a Single GPU

### 6.1 Two-Phase Caching Architecture

**Phase 1: Preprocessing Caching (Run Once)**
- Load 10 independent NVTabular workflows per fold
- Preprocess Validation and Test data on GPU, cache in RAM
- Time: ~10 minutes (~60 seconds per fold)

**Phase 2: Model Inference (Cache Reuse)**
- Reuse cached preprocessed data across 10 seed models
- Parallel prediction of 100 models (10 folds × 10 seeds) with XGBoost GPU predictor
- Time: ~3 minutes (~2 seconds per model)

Without caching: 103 minutes → With caching: **~13 minutes** (excluding Wide&Deep trained in separate environment)

### 6.2 NVTabular GPU-Accelerated Preprocessing

**GPU Transform Pipeline:**
1. Zero-copy I/O: Load Parquet files directly to GPU memory as MerlinDataset
2. GPU Operations: Parallel categorical encoding and missing value imputation on GPU
3. Efficient Transfer: Only final results transferred to CPU, minimizing data movement

---

## 7. Conclusion

Our solution achieved **final CV: 0.359380 (AP: 0.089676, WLL: 0.589612), Public LB: 0.35297, Private LB: 0.35179**, ranking **1st place overall**. Maintaining stable 1st place on both Public and Private leaderboards demonstrates robust modeling without overfitting.

### Key Contributions

1. **Production-viable Large-scale Ensemble**: Demonstrated that 36-model large-scale ensemble is operable in actual production environments using GPU acceleration with NVIDIA Merlin framework. Reduced training and inference time by 50x+ for real-time serving suitability.

2. **Effective Sequence Processing**: Efficiently processed 6,590-length ultra-long sequences with Bi-GRU and embedding projection, achieving balance between memory and performance. Validated truncation strategy through information-theoretic analysis (Cohen's d, Gini coefficient).

3. **Composite Metric Optimization**: Simultaneously optimized ranking and probability calibration with 3-stage pipeline of BCE training + AUC early stopping + Temperature scaling. A practical approach satisfying actual business requirements of both "good predictions" and "good rankings."

This solution demonstrates beyond just competition victory that GPU-accelerated recommendation systems can be practically applied in large-scale production environments. Particularly, Merlin framework introduction brings dramatic performance improvement over existing CPU-based pipelines, suggesting the possibility of drastically shortening real-time CTR prediction service update cycles.

---

## References

[1] Narasimhan, H., Vaish, R., & Agarwal, S. (2014). On the Statistical Consistency of Plug-in Classifiers for Non-decomposable Performance Measures. NIPS'14.

[2] Yan, L., et al. (2003). Optimizing Classifier Performance via an Approximation to the Wilcoxon-Mann-Whitney Statistic. ICML'03.

[3] Guo, C., et al. (2017). On Calibration of Modern Neural Networks. ICML'17.

[4] Nickolls, J., et al. (2008). Scalable Parallel Programming with CUDA. ACM Queue.

[5] Chung, J., et al. (2014). Empirical Evaluation of Gated Recurrent Neural Networks on Sequence Modeling. arXiv:1412.3555.

[6] Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate. Journal of the Royal Statistical Society.

[7] Caruana, R., et al. (2004). Ensemble Selection from Libraries of Models. ICML'04.

---

*\* Contributed to NVIDIA Merlin framework introduction, NVTabular optimization, and ~40 model ensemble baseline.*

*\*\* Contributed to Wide&Deep single model enhancement and final ensemble performance improvement through preprocessing variations.*
