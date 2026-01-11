# TalkDataOptimize

TalkDataOptimize是一个面向个人的，私人化，轻量化的多轮对话数据预处理工具，用于帮助用户轻松地处理和优化多轮对话数据，便于为后续的Lora训练或模型微调提供高质量的数据。

## 安装与使用

1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **运行程序**:
    ```bash
    python app.py
    ```

3.  **访问应用**:
    打开浏览器访问 `http://localhost:5000`。

## 目录结构说明

-   `static/`: 静态资源文件 (CSS, JS 等)。
-   `templates/`: HTML 模板文件。
-   `data/`:用于存储上传的数据集和标注结果。
    -   `uploaded/`: 存放原始上传的 JSON 数据集。
    -   `annotations/`: 存放导出的标注结果。
    -   `temp/`: 存放临时工作文件。
