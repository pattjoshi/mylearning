## Progress

- [x] Variables & Data Types | Lecture 1
- [ ] Arrays
- [ ] Linked List

## Assign operater

- right side operater assign to leftside

## Type of operator

- an operator is a symbol that perform a certain operation between operands.
- arighmetic operater (+ , - , \* , / , % , \*\*)
- relation (== , != , > , < , >= , <= )
- assignment operators ( = , += , -= , /= ,%= , \*\*=)
- logical operators ( not , and , or)
- input() bydefault convert in to string , so we manualy type casting it.


# string
## slicing
-  accessing parts  of a string .
- 

# List Methods
- list **Mutable**
- list = [2,1,3]
- list.append(4) # add one element at the end [2,1,3,4]
- list.sort() # sorts in ascending order [1,2,3]
- list.sort(reverse = True) # sorts in desending order [3,3,1]
- list.reverse() # reverses list [3,1,2]
- list.insert(idx,el) # element at index
- remove the 1st occurrence of element
- removes element at idx

# Tuples 
- A built-in data type that lets us create **immutable** sequences of values.
-  

# Dictionary in py (L4)
- Dictionaries are used to store data values in **key:value** pairs
- They are unordered,mutable(changable) **don't allow duplicate keys**


# Dictionary Methods
- myDict.keys() # return all keys
- myDict.values() # return all values
- myDict.items() #return all (key,val) pairs as tuples
- myDict.get("key") # return the key according to value
- myDict.update(newDict) # inserts the specifed items to the dictiona

# set
- set in the collection of the **unordered items**,
- Each element in the set must be **unique & immutable**.
- list and dict are store in set
- nums = {1,2,3,4}
- set.add(el) # add an element
- set.remove(el) # removes the elem an 
- set.clear() # empties the set
- set.pop() # removes a rendom value
- set.union(set2) # **combines both set values** & return new
- set.intersection(set2) # **comnines commmon values**  & return new
