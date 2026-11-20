import argparse

from store import Problem, create_admin, initialize


def main():
    parser = argparse.ArgumentParser(description="Управление учётной записью администратора портала.")
    actions = parser.add_subparsers(dest="action", required=True)
    admin = actions.add_parser("admin", help="Создать администратора или перевыпустить его пароль.")
    admin.add_argument("email")
    arguments = parser.parse_args()
    initialize()
    try:
        password = create_admin(arguments.email)
    except Problem as error:
        parser.exit(1, f"{error.message}\n")
    print("Адрес: " + arguments.email.strip().lower())
    print("Пароль портала: " + password)
    print("Скопируйте пароль для входа. Следующий запуск команды перевыпустит его и завершит старые сессии.")


if __name__ == "__main__":
    main()
