import os

def main():
    # Step 1: PDF 转换
    from topdf import batch_convert
    pdf_input_folder = r"G:\yuliaoku\新能源减排服务"
    batch_convert(pdf_input_folder)

    # Step 2: PDF 提取为 Markdown
    from duo import process_folder
    pdf_extracted_folder = r"/home/yancong/第二次语料库/books"
    pdf_output_folder = r"/home/yancong/第二次语料库/books/output"
    process_folder(pdf_extracted_folder, pdf_output_folder, num_gpus=4)

    # Step 3: Markdown 清洗
    from txtclean import process_markdown_files
    markdown_input_folder = r"G:\yuliaoku\books2\markdown"
    markdown_output_folder = r"G:\yuliaoku\books2\cleaned_markdown_files_txt"
    process_markdown_files(markdown_input_folder, markdown_output_folder)

    # Step 4: 语义去重
    from quchong2 import semantic_deduplicate
    dedup_input_file = r"G:\yuliaoku\1-quan\未去重.txt"
    dedup_output_file = r"G:\yuliaoku\1-quan\去重.txt"
    semantic_deduplicate(dedup_input_file, dedup_output_file, similarity_threshold=0.9)

    # Step 5: TXT 转 JSONL
    from  josnl import txt_to_jsonl
    txt_input_folder = r"G:\yuliaoku\books2\cleaned_markdown_files_txt"
    jsonl_output_folder = r"G:\yuliaoku\books2\jsonl"
    txt_to_jsonl(txt_input_folder, jsonl_output_folder)

    print("=== 全流程完成 ===")

if __name__ == "__main__":
    main()
