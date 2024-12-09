from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from config import DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER
Base = declarative_base()
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    gender = Column(String, index=True)
    children = relationship("ParentChild", back_populates="parent", foreign_keys="[ParentChild.parent_id]")
    parents = relationship("ParentChild", back_populates="child", foreign_keys="[ParentChild.child_id]")


class ParentChild(Base):
    __tablename__ = "parent_child"
    parent_id = Column(Integer, ForeignKey('people.id'), primary_key=True)
    child_id = Column(Integer, ForeignKey('people.id'), primary_key=True)
    parent = relationship("Person", back_populates="children", foreign_keys=[parent_id])
    child = relationship("Person", back_populates="parents", foreign_keys=[child_id])


Base.metadata.create_all(bind=engine)
