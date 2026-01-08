"""
NLP Content Analysis for BINGO365 Monitoring
Analyzes content similarity, patterns, and themes
"""
import hashlib
import re
from typing import List, Tuple, Dict
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter

# Try to import sentence-transformers for better similarity
try:
    from sentence_transformers import SentenceTransformer
    USE_SENTENCE_TRANSFORMERS = True
except ImportError:
    USE_SENTENCE_TRANSFORMERS = False
    print("sentence-transformers not installed. Using TF-IDF for similarity.")


class ContentAnalyzer:
    """Analyzes ad content for similarity and patterns"""

    def __init__(self, use_transformers=None):
        """Initialize the analyzer"""
        self.use_transformers = use_transformers if use_transformers is not None else USE_SENTENCE_TRANSFORMERS

        if self.use_transformers:
            # Use multilingual model for Filipino content
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        else:
            self.vectorizer = TfidfVectorizer(
                ngram_range=(1, 3),
                max_features=5000,
                stop_words=None  # Keep all words for Filipino content
            )

        # Common content themes/keywords
        self.theme_keywords = {
            'signup_bonus': ['sign up', 'signup', 'register', 'libreng', 'free'],
            'deposit_bonus': ['deposit', 'bonus', 'dp0sit', 'puhunan'],
            'cashback': ['cashback', 'cash back', 'balik'],
            'promo': ['promo', 'discount', 'sale', 'offer'],
            'jackpot': ['jackpot', 'panalo', 'win', 'swerte'],
            'game': ['game', 'laro', 'bingo', 'slots'],
        }

    def compute_hash(self, text: str) -> str:
        """Compute hash for content deduplication"""
        if not text:
            return ""
        # Normalize text before hashing
        normalized = self.normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove special characters but keep letters and numbers
        text = re.sub(r'[^\w\s]', '', text)
        return text

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for text"""
        if self.use_transformers:
            return self.model.encode(text)
        else:
            # Use TF-IDF for single text (fit on single document)
            return self.vectorizer.fit_transform([text]).toarray()[0]

    def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts"""
        if not text1 or not text2:
            return 0.0

        text1 = self.normalize_text(text1)
        text2 = self.normalize_text(text2)

        if text1 == text2:
            return 1.0

        if self.use_transformers:
            embeddings = self.model.encode([text1, text2])
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        else:
            try:
                tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
                similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            except:
                # Fallback to simple Jaccard similarity
                set1 = set(text1.split())
                set2 = set(text2.split())
                intersection = len(set1.intersection(set2))
                union = len(set1.union(set2))
                similarity = intersection / union if union > 0 else 0.0

        return float(similarity)

    def compute_batch_similarity(self, texts: List[str]) -> np.ndarray:
        """Compute pairwise similarity matrix for a list of texts"""
        if not texts:
            return np.array([])

        normalized = [self.normalize_text(t) for t in texts]

        if self.use_transformers:
            embeddings = self.model.encode(normalized)
            similarity_matrix = cosine_similarity(embeddings)
        else:
            tfidf_matrix = self.vectorizer.fit_transform(normalized)
            similarity_matrix = cosine_similarity(tfidf_matrix)

        return similarity_matrix

    def find_similar_content(self, target_text: str, content_list: List[dict],
                            threshold: float = 0.5) -> List[dict]:
        """Find content similar to target text"""
        results = []
        target_normalized = self.normalize_text(target_text)

        for content in content_list:
            content_text = content.get('primary_content', '')
            if not content_text:
                continue

            similarity = self.compute_similarity(target_text, content_text)

            if similarity >= threshold:
                results.append({
                    **content,
                    'similarity_score': round(similarity, 4)
                })

        # Sort by similarity score descending
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results

    def detect_theme(self, text: str) -> List[str]:
        """Detect themes/categories in content"""
        if not text:
            return []

        text_lower = text.lower()
        detected_themes = []

        for theme, keywords in self.theme_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    detected_themes.append(theme)
                    break

        return detected_themes

    def analyze_content_patterns(self, contents: List[dict]) -> Dict:
        """Analyze patterns across multiple content pieces"""
        if not contents:
            return {}

        # Extract all texts
        texts = [c.get('primary_content', '') for c in contents if c.get('primary_content')]

        if not texts:
            return {}

        # Theme distribution
        all_themes = []
        for text in texts:
            all_themes.extend(self.detect_theme(text))
        theme_counts = Counter(all_themes)

        # Content type distribution
        types = [c.get('content_type', 'Unknown') for c in contents]
        type_counts = Counter(types)

        # Compute similarity matrix
        similarity_matrix = self.compute_batch_similarity(texts)

        # Find duplicates (similarity > 0.85)
        duplicate_pairs = []
        unique_count = len(texts)
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if similarity_matrix[i][j] > 0.85:
                    duplicate_pairs.append((i, j, similarity_matrix[i][j]))
                    unique_count -= 1

        # Average similarity
        if len(texts) > 1:
            # Get upper triangle of matrix (excluding diagonal)
            upper_tri = similarity_matrix[np.triu_indices(len(texts), k=1)]
            avg_similarity = np.mean(upper_tri) if len(upper_tri) > 0 else 0
        else:
            avg_similarity = 0

        return {
            'total_content': len(texts),
            'unique_content': max(unique_count, 1),
            'duplicate_pairs': len(duplicate_pairs),
            'avg_similarity': round(avg_similarity, 4),
            'freshness_score': round(unique_count / len(texts) * 100, 1) if texts else 0,
            'theme_distribution': dict(theme_counts),
            'type_distribution': dict(type_counts),
        }

    def compare_daily_vs_monthly(self, daily_content: List[dict],
                                  monthly_content: List[dict]) -> Dict:
        """Compare today's content with monthly content"""
        if not daily_content or not monthly_content:
            return {
                'daily_total': len(daily_content) if daily_content else 0,
                'monthly_total': len(monthly_content) if monthly_content else 0,
                'new_content_count': 0,
                'recycled_count': 0,
                'matches': []
            }

        matches = []
        new_content = []

        for daily in daily_content:
            daily_text = daily.get('primary_content', '')
            if not daily_text:
                continue

            # Find best match in monthly content
            best_match = None
            best_score = 0

            for monthly in monthly_content:
                monthly_text = monthly.get('primary_content', '')
                if not monthly_text:
                    continue

                # Skip if it's the same record
                if daily.get('id') == monthly.get('id'):
                    continue

                score = self.compute_similarity(daily_text, monthly_text)
                if score > best_score:
                    best_score = score
                    best_match = monthly

            if best_score >= 0.7:  # Similar content found
                matches.append({
                    'daily_content': daily_text[:100] + '...' if len(daily_text) > 100 else daily_text,
                    'daily_date': daily.get('date'),
                    'matched_content': best_match.get('primary_content', '')[:100] + '...',
                    'matched_date': best_match.get('date'),
                    'similarity': round(best_score, 4),
                    'status': 'duplicate' if best_score >= 0.85 else 'similar'
                })
            else:
                new_content.append(daily)

        return {
            'daily_total': len(daily_content),
            'monthly_total': len(monthly_content),
            'new_content_count': len(new_content),
            'recycled_count': len(matches),
            'freshness_rate': round(len(new_content) / len(daily_content) * 100, 1) if daily_content else 0,
            'matches': matches
        }


# Singleton instance
_analyzer = None


def get_analyzer():
    """Get singleton analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ContentAnalyzer()
    return _analyzer


if __name__ == "__main__":
    # Test the analyzer
    analyzer = ContentAnalyzer(use_transformers=False)

    # Test similarity
    text1 = "Sayang ang 8,888 Sign Up Bonus kung palalampasin mo pa! Register na!"
    text2 = "Wag papalampasin ang swerte! Lalo na kung may libreng pamuhunan! Kunin ang 36.5 signup bonus!"
    text3 = "Download the app now!"

    print(f"Similarity (text1 vs text2): {analyzer.compute_similarity(text1, text2):.4f}")
    print(f"Similarity (text1 vs text3): {analyzer.compute_similarity(text1, text3):.4f}")

    # Test theme detection
    print(f"Themes in text1: {analyzer.detect_theme(text1)}")
    print(f"Themes in text2: {analyzer.detect_theme(text2)}")
