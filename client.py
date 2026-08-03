import subprocess
import sys
import requests

SERVER_URL = "http://localhost:3007"
session = requests.Session()
session.auth = ("demo", "demo")  # replace with real login later


def clear_screen():
    subprocess.run(["cls"]) if sys.platform == "win32" else subprocess.run(["clean"])  # os.system is deprecated apparently


def invalid_choice(choice):
    print(f"Your choice ({choice}) is invalid.")
    input("Enter to continue...")


def api_get(path):
    resp = session.get(f"{SERVER_URL}{path}")
    return resp


def api_post(path, json=None):
    resp = session.post(f"{SERVER_URL}{path}", json=json or {})
    return resp


def check_server_status():
    try:
        resp = session.get(f"{SERVER_URL}/boards", timeout=2)
        if resp.status_code == 200:
            return f"Server {SERVER_URL}: connected."
        else:
            return f"Server {SERVER_URL}: connected (status {resp.status_code})."
    except requests.exceptions.ConnectionError:
        return f"Server {SERVER_URL}: couldn't connect."
    except requests.exceptions.Timeout:
        return f"Server {SERVER_URL}: couldn't connect (timeout)."


def new_board():
    while True:
        clear_screen()
        print("== New Board\n")
        board_name = str(input("Please enter the Board name: "))

        try:
            resp = api_post("/boards", {"name": board_name})
        except requests.exceptions.ConnectionError:
            print("Could not reach the server. Is it running?")
            input("Enter to continue...")
            return

        if resp.status_code != 201:
            error = resp.json().get("error", "Unknown error.")
            print(f"Something went wrong: {error}")
            input("Enter to continue...")
            continue

        board = resp.json()
        print(f"Successfully created Board '{board['name']}'.")
        return


def new_task(board_id):
    while True:
        clear_screen()
        print("== New Task\n")
        title = str(input("Please enter the Task title: "))

        try:
            resp = api_post(f"/boards/{board_id}/tasks", {"title": title})
        except requests.exceptions.ConnectionError:
            print("Could not reach the server. Is it running?")
            input("Enter to continue...")
            return

        if resp.status_code != 201:
            error = resp.json().get("error", "Unknown error.")
            print(f"Something went wrong: {error}")
            input("Enter to continue...")
            continue

        task = resp.json()
        print(f"Successfully created Task '{task['title']}'.")
        return


def menu_tasks(board_id, board_name):
    show_id = False
    while True:
        clear_screen()
        if show_id == False:
            print(f"== {board_name}")
            print("ID: -hidden-\n")
            print("X - [Back]")
            print("B - [Show ID]")
        else:
            print(f"== {board_name}")
            print(f"ID: {board_id}\n")
            print("X - [Back]")
            print("B - [Hide ID]")
        print("0 - [New Task]")

        try:
            resp = api_get(f"/boards/{board_id}/tasks")
        except requests.exceptions.ConnectionError:
            print("Could not reach the server. Is it running?")
            input("Enter to continue...")
            return

        tasks = resp.json() if resp.status_code == 200 else []

        for i, task in enumerate(tasks, start=1):
            mark = "x" if task["done"] else " "
            print(f"{i} - [{mark}] {task['title']}")

        choice = str(input("\nYour choice > "))

        match choice.lower():
            case "0":
                new_task(board_id)
            case "x":
                return
            case "b":
                if show_id == False: show_id=True
                else: show_id=False
                clear_screen()

            case _ if choice.isdigit() and 1 <= int(choice) <= len(tasks):
                task = tasks[int(choice) - 1]
                api_post(f"/boards/{board_id}/tasks/{task['id']}/toggle")
            case _:
                invalid_choice(choice)


def menu_boards():
    while True:
        clear_screen()
        print("== Boards\n")
        print("X - [Back]")
        print("0 - [New Board]")

        try:
            resp = api_get("/boards")
        except requests.exceptions.ConnectionError:
            print("Could not reach the server. Is it running?")
            input("Enter to continue...")
            return

        boards = resp.json() if resp.status_code == 200 else []

        for i, board in enumerate(boards, start=1):
            print(f"{i} - {board['name']}")

        choice = str(input("\nYour choice > "))

        match choice.lower():
            case "0":
                new_board()
            case "x":
                return
            case _ if choice.isdigit() and 1 <= int(choice) <= len(boards):
                board = boards[int(choice) - 1]
                menu_tasks(board["id"], board["name"])
            case _:
                invalid_choice(choice)


def menu_main():
    while True:
        clear_screen()
        print("== questi")
        print(check_server_status())
        print("Logged in as [demo]\n")
        print("1 - Boards")
        print("X - Exit")

        choice = str(input("\nYour choice > "))

        match choice.lower():
            case "1":
                menu_boards()
            case "x":
                quit()
            case _:
                invalid_choice(choice)


menu_main()