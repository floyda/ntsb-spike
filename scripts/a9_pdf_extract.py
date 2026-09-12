"""A9 spike check: text-extraction quality of an NTSB docket PDF using pypdf."""
import sys
from pypdf import PdfReader


def main(path: str, sample_pages: int = 2, sample_chars: int = 1500) -> None:
    reader = PdfReader(path)
    n_pages = len(reader.pages)
    texts = [page.extract_text() or "" for page in reader.pages]
    total = sum(len(t) for t in texts)

    print(f"file: {path}")
    print(f"pages: {n_pages}")
    print(f"total extracted chars: {total}")
    print(f"chars per page: {[len(t) for t in texts]}")
    print(f"mean chars/page: {total / n_pages:.0f}")

    for i in range(min(sample_pages, n_pages)):
        print(f"\n===== page {i + 1} (first {sample_chars} chars of {len(texts[i])}) =====")
        print(texts[i][:sample_chars])


if __name__ == "__main__":
    main(sys.argv[1])
