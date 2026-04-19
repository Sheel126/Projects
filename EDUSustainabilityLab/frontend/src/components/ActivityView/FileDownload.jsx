import { useState, useEffect } from "react";

function FileDownload({ fileId }) {
    const [isDownloading, setIsDownloading] = useState(false);
    const [fileName, setFileName] = useState("");
    const [fileType, setFileType] = useState("");
    const [filePreviewUrl, setFilePreviewUrl] = useState("");

    useEffect(() => {
        async function fetchFileDetails() {
            try {
                // Fetch file metadata (name & type)
                const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/file-info/${fileId}/`);
                if (!response.ok) throw new Error("Failed to fetch file details");

                const data = await response.json();
                setFileName(data.file_name);
                setFileType(determineFileType(data.file_type));

                // Fetch the actual file as a Blob for PDFs
                if (["pdf"].includes(data.file_type)) {
                    const fileResponse = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/download/${fileId}/`);
                    if (!fileResponse.ok) throw new Error("Failed to fetch file");

                    const blob = await fileResponse.blob();
                    const objectUrl = URL.createObjectURL(blob);
                    setFilePreviewUrl(objectUrl);
                } else {
                    setFilePreviewUrl(`${process.env.REACT_APP_BACKEND_URL}/api/download/${fileId}/`);
                }
            } catch (error) {
                console.error("Error fetching file info:", error);
            }
        }

        if (fileId) {
            fetchFileDetails();
        }
    }, [fileId]);

    function determineFileType(extension) {
        if (["png", "jpg", "jpeg"].includes(extension)) return "image";
        if (extension === "pdf") return "pdf";
        if (extension === "docx") return "docx";
        return "unknown";
    }

    async function handleDownload() {
        setIsDownloading(true);
        try {
            const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/download/${fileId}/`);
            if (!response.ok) throw new Error("Failed to download file");

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = objectUrl;
            link.download = fileName || "downloaded_file";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error("Error downloading file:", error);
        }
        setIsDownloading(false);
    }

    return (
        <section className="flex flex-col gap-4 items-center p-6 rounded-lg shadow bg-white max-w-lg w-full">
            <div className="w-full h-[650px] border border-gray-300 flex items-center justify-center overflow-hidden bg-gray-100">
                {filePreviewUrl ? (
                    fileType === "image" ? (
                        <img src={filePreviewUrl} alt="Preview" className="w-full h-full object-contain" />
                    ) : fileType === "pdf" ? (
                        <iframe src={filePreviewUrl} className="w-full h-full object-contain"></iframe>
                    ) : fileType === "docx" ? (
                        <p className="text-gray-500">Preview not available for DOCX</p>
                    ) : (
                        <p className="text-gray-500">Unsupported file type</p>
                    )
                ) : (
                    <p className="text-gray-500">Loading file...</p>
                )}
            </div>

            <div className="flex space-x-4 font-semibold w-full">
                <label
                    onClick={handleDownload}
                    className="cursor-pointer border-2 bg-green-700 border-green-700 text-white py-2 px-6 rounded-lg text-center hover:bg-green-800 hover:border-green-800 hover:text-white transition duration-300 w-full"
                    disabled={isDownloading}
                >
                    {isDownloading ? "Downloading..." : "Download"}
                </label>
            </div>
        </section>
    );
}

export default FileDownload;
