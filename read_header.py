def read_header():
    with open('data/realtime_ecommerce_2025.csv', 'r') as f:
        header = f.readline().strip()
        cols = header.split(',')
        for col in cols:
            print(col)

if __name__ == "__main__":
    read_header()
