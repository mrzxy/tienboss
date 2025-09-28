send_history = [1,2,3,4]
def a():
    if len(send_history) > 2:
        send_history[:] = send_history[-2:]
a()
print(send_history)
send_history.append(5)
a()
print(send_history)