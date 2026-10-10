import re

with open('app/db/models.py', 'r') as f:
    content = f.read()

# Add imports
content = content.replace(
    "from sqlalchemy.orm import declarative_base, relationship",
    "from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column"
)

# Replacements for Columns
# id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) -> id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

replacements = [
    (r"id = Column\(UUID\(as_uuid=True\)(.*?)\)", r"id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True)\1)"),
    (r"payment_id = Column\(UUID\(as_uuid=True\)(.*?)\)", r"payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True)\1)"),
    (r"event_id = Column\(UUID\(as_uuid=True\)(.*?)\)", r"event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True)\1)"),
    (r"txn_id = Column\(UUID\(as_uuid=True\)(.*?)\)", r"txn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True)\1)"),
    
    (r"(\w+) = Column\(String(\(.*?\))?(.*?)\)", r"\1: Mapped[str] = mapped_column(String\2\3)"),
    (r"(\w+) = Column\(Text(.*?)\)", r"\1: Mapped[str] = mapped_column(Text\2)"),
    (r"(\w+) = Column\(BigInteger(.*?)\)", r"\1: Mapped[int] = mapped_column(BigInteger\2)"),
    (r"(\w+) = Column\(Integer(.*?)\)", r"\1: Mapped[int] = mapped_column(Integer\2)"),
    (r"(\w+) = Column\(DateTime(\(.*?\))?(.*?)\)", r"\1: Mapped[datetime] = mapped_column(DateTime\2\3)"),
    (r"(\w+) = Column\(JSONB(.*?)\)", r"\1: Mapped[dict] = mapped_column(JSONB\2)"),
]

for pattern, repl in replacements:
    content = re.sub(pattern, repl, content)

with open('app/db/models.py', 'w') as f:
    f.write(content)
