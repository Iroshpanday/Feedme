import nltk

def download_nltk_data():
    required_data = [
        ('tokenizers/punkt', 'punkt'),
        ('corpora/stopwords', 'stopwords'),
        ('corpora/wordnet', 'wordnet'),
        ('taggers/averaged_perceptron_tagger', 'averaged_perceptron_tagger'),
        ('corpora/omw-1.4', 'omw-1.4')
    ]

    for path, package in required_data:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(package)
