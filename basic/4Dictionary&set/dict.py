# Dictionary
info = {
    "name": "om prakash",
    "learning": "coding",
    "age": 23,
    "is_adult": True,
    "language": ["python", "javaScript"],
    "wishList": ("ujain", "Risikes"),
    12.43: "12.46",
}

print(info["age"])

null_dict = {}
null_dict["movi"] = "Om shanti om"
print(null_dict)


student = {
    "name": "om prakash pattjoshi",
    "subjects": {"phy": 78, "chm": 98, "math": 78},
}

print(student["subjects"]["chm"])
print(student.keys(), "-> return keys")
print(student.values(), "-> return values")
