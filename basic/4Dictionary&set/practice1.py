# sorte a following word meaning in  a python dectionary :
# table : "a piece of furniture", "list of facts & figures"
# cat : "a small animal"


dictionary = {
    "table": ["a piece of furniture", "list of facts & figures"],
    "cat": "small animal",
}


# Q2 :- you are given a list of subjects for students. Assume one classroom is required for 1 subject. How many callroms are need by all student .

subject = ["python", "javaScript", "c++", "javaScript", "c++"]

print(len(list(set((subject)))))


# soore both value 9 and 9.0 without data type

value = {"flot": 9.0, "int": 9}
print(value)
