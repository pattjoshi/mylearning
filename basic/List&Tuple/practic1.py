# WAP To ask the user to enter names of their 3 fevrite movies & store them in a list.

# fevorite = []

# user = input("enter you 3 Fevorit movies: ")
# fevorite.append(user)
# print(fevorite)

# WAP to check if a list contains a palindrom of element.
# palindrome means :- reading from start is same as back
#

orginal = [1, 2, 1, 22]
new_list = orginal.copy()
new_list.reverse()

if orginal == new_list:
    print("palimdrun")
else:
    print("Not Palimdrum")
