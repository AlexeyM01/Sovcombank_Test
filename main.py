from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import SessionLocal, Person, ParentChild
import networkx as nx
import matplotlib.pyplot as plt
from io import BytesIO

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_parent_child_relationship(db: Session, parent_id: int, child_id: int):
    parent = db.query(Person).filter(Person.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail=f"Parent with id {parent_id} not found")
    if parent.gender not in ['male', 'female']:
        raise HTTPException(status_code=400, detail=f"Parents gender must be male or female")
    existing_relationship = db.query(ParentChild).filter(
        ParentChild.parent_id == parent_id,
        ParentChild.child_id == child_id).first()
    if existing_relationship:
        return None
    parent_child = ParentChild(parent_id=parent_id, child_id=child_id)
    db.add(parent_child)
    db.commit()


@app.post("/add_relationship/")
def add_relationship(parent_id: int, child_id: int, db: Session = Depends(get_db)):
    create_parent_child_relationship(db, parent_id, child_id)
    return {"detail": f"Created relation between ID {parent_id} and ID {child_id}"}


@app.post("/add_person/")
def add_person(name: str, gender: str, mother_id: int = None, father_id: int = None, db: Session = Depends(get_db)):
    if gender not in ["male", "female"]:
        raise HTTPException(status_code=400, detail=f"Gender must be 'male' or 'female'")
    try:
        new_person = Person(name=name, gender=gender)
        db.add(new_person)
        db.commit()
        db.refresh(new_person)
        if mother_id:
            if db.query(Person).filter(Person.id == mother_id).first().gender != "female":
                raise HTTPException(status_code=400, detail=f"The mother must be female")
            create_parent_child_relationship(db, mother_id, new_person.id)
        if father_id:
            if db.query(Person).filter(Person.id == father_id).first().gender != "male":
                raise HTTPException(status_code=400, detail=f"The father must be male")
            create_parent_child_relationship(db, father_id, new_person.id)
        return {"detail": f"Created new person with ID {new_person.id}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not create person: " + str(e))


@app.delete("/delete_connection/")
def delete_connection(person_id: int, parent_id: int = None, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail=f"Person is not found")
    try:
        if parent_id is None:  # удаление всех существующих связей у текущего человека
            db.query(ParentChild).filter((ParentChild.parent_id == person_id) | (ParentChild.child_id == person_id)
                                         ).delete(synchronize_session='fetch')
            return {"detail": f"Person ID {person_id} deleted"}
        else:  # удаление только одной существующей связи между родителем и ребенком
            connection = db.query(ParentChild).filter(
                (ParentChild.parent_id == parent_id) & (ParentChild.child_id == person_id)).first()
            if connection:
                db.query(ParentChild).filter((ParentChild.parent_id == parent_id) & (ParentChild.child_id == person_id)
                                             ).delete(synchronize_session='fetch')
                db.commit()
                return {"detail": f"Connection between person {person_id} and {parent_id} deleted"}
            else:
                raise HTTPException(status_code=400, detail=f"Connection is not found")
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete person: " + str(error))


@app.delete("/delete_person/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail=f"Person {person_id} is not found")
    try:
        db.query(ParentChild).filter((ParentChild.parent_id == person_id) | (ParentChild.child_id == person_id)
                                     ).delete(synchronize_session='fetch')
        db.delete(person)
        db.commit()
        return {"detail": f"Person ID {person_id} deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete person: " + str(e))


@app.get("/family_member_count/{person_id}")
def family_member_count(person_id: int, db: Session = Depends(get_db)):
    family_members = set()
    family_members.add(person_id)
    descendants = get_descendants(person_id, db)
    for child in descendants:
        family_members.add(child.id)
    ancestors = get_ancestors(person_id, db)
    for parent in ancestors:
        family_members.add(parent.id)
    return {"family_member_count": len(family_members)}


@app.get("/generation_count/{person_id}")
def generation_count(person_id: int, db: Session = Depends(get_db)):
    generation_set = set()

    def count_generations(current_id, current_generation):
        generation_set.add(current_generation)
        parent_records = db.query(ParentChild).filter(ParentChild.child_id == current_id).all()
        for record in parent_records:
            count_generations(record.parent_id, current_generation + 1)

    ancestors = get_ancestors(person_id, db)
    for ancestor in ancestors:
        count_generations(ancestor.id, 1)

    return {"generation_count": len(generation_set)}


@app.get("/male_relatives_count/{person_id}")
def male_relatives_count(person_id: int, db: Session = Depends(get_db)):
    descendants = get_descendants(person_id, db)
    descendants_male_count = sum(1 for person in descendants if person.gender == "male")
    ancestors = get_ancestors(person_id, db)
    ancestors_male_count = sum(1 for person in ancestors if person.gender == "male")
    person = db.query(Person).filter(Person.id == person_id).first()
    return {"male_relatives_count": descendants_male_count + ancestors_male_count + person.gender == "male"}


@app.get("/female_relatives_count/{person_id}")
def female_relatives_count(person_id: int, db: Session = Depends(get_db)):
    descendants = get_descendants(person_id, db)
    descendants_male_count = sum(1 for person in descendants if person.gender == "female")
    ancestors = get_ancestors(person_id, db)
    ancestors_male_count = sum(1 for person in ancestors if person.gender == "female")
    person = db.query(Person).filter(Person.id == person_id).first()
    return {"male_relatives_count": descendants_male_count + ancestors_male_count + person.gender == "female"}


def get_descendants(person_id: int, db: Session):
    descendants = []
    child_records = db.query(ParentChild).filter(ParentChild.parent_id == person_id).all()
    for record in child_records:
        child = db.query(Person).filter(Person.id == record.child_id).first()
        if child:
            descendants.append(child)
            descendants.extend(get_descendants(child.id, db))
    return descendants


def get_ancestors(person_id: int, db: Session):
    ancestors = []
    parent_records = db.query(ParentChild).filter(ParentChild.child_id == person_id).all()
    for record in parent_records:
        parent = db.query(Person).filter(Person.id == record.parent_id).first()
        if parent:
            ancestors.append(parent)
            ancestors.extend(get_ancestors(parent.id, db))
    return ancestors


@app.get("/family_tree/{person_id}")
def family_tree(person_id: int, db: Session = Depends(get_db)):
    ancestors = get_ancestors(person_id, db)
    descendants = get_descendants(person_id, db)
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")
    G = nx.DiGraph()
    G.add_node(person.id, name=f"{person.name} ({person.gender})")
    for ancestor in ancestors:
        G.add_node(ancestor.id, name=f"{ancestor.name} ({ancestor.gender})")
        G.add_edge(ancestor.id, person.id)
    for descendant in descendants:
        G.add_node(descendant.id, name=f"{descendant.name} ({descendant.gender})")
        G.add_edge(person.id, descendant.id)
    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, labels=nx.get_node_attributes(G, 'name'), node_size=3000, node_color='skyblue')
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return StreamingResponse(buf, media_type="image/png")
