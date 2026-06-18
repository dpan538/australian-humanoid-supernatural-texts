from aus_humanoid.dedupe import title_similarity, token_overlap


def test_token_overlap_detects_shared_title_terms():
    score = token_overlap("The Yowie in Queensland", "Yowie in Queensland")
    assert 0.7 <= score <= 1.0


def test_title_similarity_handles_near_duplicates():
    score = title_similarity("A strange hairy man in the bush", "Strange hairy man in bush")
    assert score >= 0.9


def test_title_similarity_returns_zero_for_missing_titles():
    assert title_similarity("", "Yowie report") == 0.0

