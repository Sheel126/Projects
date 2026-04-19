import { useState } from "react";

function FileUpload({ onFileUpload }) {
    const [fileUrl, setFileUrl] = useState(null);
    const [fileType, setFileType] = useState(null);
    const [fileName, setFileName] = useState("");
    const [dragActive, setDragActive] = useState(false);

    function handleFileUpload(file) {
        if (!file) return;

        const url = URL.createObjectURL(file);
        setFileUrl(url);
        setFileName(file.name);

        if (file.type.startsWith("image/")) {
            setFileType("image");
        } else if (file.type === "application/pdf") {
            setFileType("pdf");
        } else if (file.name.endsWith(".docx")) {
            setFileType("docx");
        } else {
            alert("Unsupported file format. Please upload PNG, JPG, PDF, or DOCX.");
            setFileUrl(null);
            setFileType(null);
            setFileName("");
            onFileUpload(null); // Inform parent that no valid file is selected
            return;
        }

        onFileUpload(file); // Pass the selected file to parent
    }

    function handleFileChange(event) {
        const file = event.target.files[0];
        handleFileUpload(file);
    }

    function handleDrop(event) {
        event.preventDefault();
        setDragActive(false);
        const file = event.dataTransfer.files[0];
        handleFileUpload(file);
    }

    function handleRemoveFile() {
        setFileUrl(null);
        setFileType(null);
        setFileName("");
        onFileUpload(null); // Inform parent that file was removed
    }

    return (
        <section className="flex flex-col gap-4 items-center p-6 rounded-lg shadow bg-white max-w-lg w-full">
            <div
                className={`w-full h-[650px] aspect-w-16 aspect-h-9 border border-gray-300 flex items-center justify-center overflow-hidden bg-gray-100 
                    ${dragActive ? "border-2 border-blue-500 bg-blue-100" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
            >
                {fileUrl ? (
                    fileType === "image" ? (
                        <img src={fileUrl} className="w-full h-full object-contain" />
                    ) : fileType === "pdf" ? (
                        <iframe src={fileUrl} className="w-full h-full object-contain"></iframe>
                    ) : fileType === "docx" ? (
                        <a href={fileUrl} download={fileName} className="text-blue-500 underline">
                            Download {fileName}
                        </a>
                    ) : null
                ) : (
                    <div className="flex flex-col gap-4 text-gray-500 text-center">
                        <p>
                            <span className="font-semibold">Drag & Drop</span> your file or click <span className="font-semibold">Upload</span>
                        </p>
                        <p className="font-medium">Accepted file types: JPG, JPEG, PNG, PDF, DOCX</p>
                    </div>
                )}
            </div>
            <input
                id="fileUpload"
                type="file"
                name="file"
                onChange={handleFileChange}
                accept=".png, .jpg, .jpeg, .pdf, .docx"
                className="hidden"
            />
            <div className="flex space-x-4 font-semibold w-full">
                <label
                    htmlFor="fileUpload"
                    className={`cursor-pointer py-2 px-6 rounded-lg text-center transition duration-300 border-2 border-green-700 hover:border-green-800 hover:bg-green-800 w-full
                            ${fileUrl ? "text-green-700 hover:text-white" : "bg-green-700 text-white "}`}
                >
                    Upload
                </label>

                {fileUrl && (
                    <label
                        onClick={handleRemoveFile}
                        className="cursor-pointer border-2 border-red-600 text-red-600 py-2 px-6 rounded-lg text-center hover:bg-red-600 hover:text-white transition duration-300 w-full"
                    >
                        Remove
                    </label>
                )}
            </div>
        </section>
    );
}

export default FileUpload;
