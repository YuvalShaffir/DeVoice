SEPARATE_PATH = "/separate"
STEM_PATH = "/stem/{content_hash}/{stem}"
TOKEN_HEADER = "X-Auth-Token"


def extension_origin(extension_id: str) -> str:
    return f"chrome-extension://{extension_id}"
