"""Vector retrieval tool over Milvus Lite. (stub)"""


def retrieve_passages(question: str, papers: list[dict], k: int = 5) -> list[dict]:
    # TODO: chunk + embed paper text, insert into Milvus (db.vector_store), search top-k.
    return [{"text": "[stub passage]", "source": p.get("title"), "url": p.get("url")} for p in papers[:k]]
