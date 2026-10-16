import sys
name = input("Imię: ")
print("Cześć", name)
sys.stdout.write("Linia: ")
line = sys.stdin.readline()
sys.stderr.write(line)
