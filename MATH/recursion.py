#defining an function to run from 1 to N

# Head Recursion 


# def func (i,n):
#     if i > n :
#         return
#     print (i)
#     func (i+1 , n)
# func (1, 20)


# # Tail Recursion [ Backtracking ] using Tail N to 1

# def func(i,n) :
#     if i >n : 
#         return 
#     func (i+1 , n)
#     print (i)
# func (1, 5)

def func (n):
    if n == 0:
        return
    print (n)
    func (n-1)
func (8)