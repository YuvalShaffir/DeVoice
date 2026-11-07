SEPARATE_PATH = "/separate"
STEM_PATH = "/stem/{content_hash}/{stem}"
TOKEN_HEADER = "X-Auth-Token"
CONTENT_TYPE_HEADER = "Content-Type"
WAV_MEDIA_TYPE = "audio/wav"
INVALID_AUDIO = "invalid audio"


def extension_origin(extension_id: str) -> str:
    return f"chrome-extension://{extension_id}"
