# Academic Research & Datasets

This document catalogs academic datasets, NLP models, and knowledge-graph approaches that are highly relevant to building the CarRec Knowledge Base, specifically for processing experiential knowledge (reviews, opinions, reliability). 

*Note: Kaggle datasets are explicitly excluded per project requirements.*

## 1. MuSe-CaR & MuSe-CarASTE
* **Type:** Research / Development Resource
* **Contents:** Multimodal Sentiment Analysis in Car Reviews. Contains over 36 hours of annotated automotive review footage, transcripts, and sentiment labels. The **MuSe-CarASTE** extension focuses specifically on Aspect Sentiment Triplet Extraction (e.g., mapping `gearbox` -> `rubbish` -> `Negative`).
* **Country/Market:** Global/Mixed (English).
* **Licensing:** Academic/Research (typically via Zenodo / institutional requests).
* **Usefulness for CarRec:** **High**. This is the gold standard for training our Aspect-Based Sentiment Analysis (ABSA) models to parse Team-BHP and Autocar reviews.
* **Classification:** Research/Development Resource (Do not use as production facts, use to train the NLP pipelines).

## 2. Automotive Ontology / Schema.org/Car
* **Type:** Background Only / Architecture Design
* **Contents:** Official web schemas (Schema.org/Car, Vehicle) developed in collaboration with automotive industry consortiums (e.g., W3C Automotive Ontology).
* **Usefulness for CarRec:** **Very High**. We should model our internal Knowledge Base schema (Graph/JSON) directly against `Schema.org/Car` to ensure future interoperability, standardizing concepts like `bodyType`, `fuelType`, `accelerationTime`, and `wheelbase`.
* **Classification:** Research/Development Resource.

## 3. SemEval ABSA Tasks (Various Years)
* **Type:** Research / Development Resource
* **Contents:** Standardized datasets for Aspect-Based Sentiment Analysis (often focusing on restaurants and laptops, but highly transferrable).
* **Usefulness for CarRec:** **Moderate**. Useful for validating the general NLP architecture before fine-tuning on automotive-specific data.
* **Classification:** Research/Development Resource.

## 4. Proprietary Forum Scrapes (Unannotated)
* **Type:** Production Candidate (To-be-built)
* **Contents:** We will need to build our own corpus of Team-BHP long-term ownership threads to run through our fine-tuned ABSA models. 
* **Usefulness for CarRec:** This will become our actual production dataset for the "Reliability" and "Owner Experience" vectors in the Knowledge Base.
* **Classification:** Production Candidate.
