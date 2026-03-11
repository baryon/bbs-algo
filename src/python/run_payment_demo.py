from bbs_payment_mvp import demo_scenarios, pretty


def main() -> None:
    for name, payload in demo_scenarios():
        print(f"== {name} ==")
        print(pretty(payload))


if __name__ == "__main__":
    main()
