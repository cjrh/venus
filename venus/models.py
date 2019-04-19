from dataclasses import dataclass


@dataclass
class Message:
    level: bytes
    message: bytes
