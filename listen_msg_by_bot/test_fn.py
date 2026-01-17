def isIllicitWord(content):
    keywords = ['习近平','李强']
    return any(keyword in content for keyword in keywords)

if __name__ == "__main__":
    print(isIllicitWord("习厉害"))
