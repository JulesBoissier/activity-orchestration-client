from src.lifecycle import ApplicationLifecycle

if __name__ == "__main__":
    app = ApplicationLifecycle(period=2)
    app.run()
