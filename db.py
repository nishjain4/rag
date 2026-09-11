import chromadb

client = chromadb.PersistentClient(path="./chroma_index")

collection = client.get_collection("documents")


data = collection.get()
print(data)
