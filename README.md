# 🧠 splain

> Understand any shell command instantly.

`splain` is a simple CLI tool that takes a command and explains it in plain English — including flags, arguments, and overall behavior.

---

## ✨ Features

* 🔍 Breaks down any shell command
* 🏷 Explains individual flags (`-a`, `--verbose`, etc.)
* 📦 Identifies arguments and their roles
* 🧠 Beginner-friendly explanations
* ⚡ Fast and lightweight
* 🔧 Extensible command database

---

## 🚀 Installation

### Option 1: Clone and run

```bash
git clone https://github.com/yourusername/splain.git
cd splain
pip install -r requirements.txt
```

### Option 2: (Optional) Install globally

```bash
pip install .
```

---

## 💡 Usage

```bash
python3 -m splain --provider "yourprovider (openai or ollama)" --model "your model" "your command"
example : 
python3 -m explain --provider ollama --model llama3.1 "tar -xzvf file.tar.gz"
```

### Example Output

```
Command: tar -xzvf file.tar.gz

Description:
Create or extract archive files

Flags:
-x → Extract files
-z → Use gzip compression
-v → Verbose mode (show progress)
-f → Specify filename

Argument:
file.tar.gz → Archive file to extract

Summary:
This command extracts the contents of 'file.tar.gz' using gzip compression and displays progress in the terminal.
```

---

## ⚙️ Options

```
splain "<command>" [options]
```

| Option  | Description              |
| ------- | ------------------------ |
| --short | Show shorter explanation |
| --json  | Output as JSON           |
| --help  | Show help menu           |

---

## 🧩 How It Works

1. Parses the command into:

   * base command
   * flags (including grouped flags like `-xzvf`)
   * arguments

2. Matches against a built-in command database

3. Generates a structured explanation

---

---

## 🔮 Roadmap

* [ ] Support more shell commands
* [ ] AI-powered explanations
* [ ] Command suggestions
* [ ] Interactive mode
* [ ] Plugin system

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo
2. Create a new branch
3. Make your changes
4. Submit a pull request

---

## 🪪 License

MIT License

---

## 💬 Inspiration

Ever copied a command from the internet and had no idea what it does?

`splain` fixes that.

---

## ⭐ Support

If you like this project, give it a star ⭐ on GitHub!
