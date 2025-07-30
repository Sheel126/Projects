import React, { useState, useEffect } from "react";

function ImageUpload({ desc, onImageUpload, generateAiImage, aiImageFile, isLoading }) {
    const [fileUrl, setFileUrl] = useState(null);
    const [fileType, setFileType] = useState(null);
    const [dragActive, setDragActive] = useState(false);

    useEffect(() => {
        if (aiImageFile) {
            handleFileUpload(aiImageFile);
        }
    }, [aiImageFile]);

    function handleFileUpload(file) {
        if (!file) return;

        const url = URL.createObjectURL(file);
        setFileUrl(url);

        if (file.type.startsWith("image/")) {
            setFileType("image");
            onImageUpload(file);
        } else {
            alert("Unsupported file format. Please upload PNG or JPG.");
            setFileUrl(null);
            setFileType(null);
            onImageUpload(null);
        }
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
        onImageUpload(null);
    }

    return (
        <section className="flex flex-col gap-4 items-center rounded-lg bg-white md:max-w-md w-full justify-center self-center">
            <div
                className={`w-full h-[320px] aspect-w-4 aspect-h-3 border border-gray-300 flex items-center justify-center overflow-hidden bg-gray-100 
                ${dragActive ? "border-2 border-blue-500 bg-blue-100" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
            >
                {isLoading ? ( 
                    <p className="text-gray-500 font-medium">Generating AI Image...</p> 
                ) : fileUrl ? (
                    <img src={fileUrl} className="w-full h-full object-contain" alt="Uploaded file" />
                ) : (
                    <div className="flex flex-col gap-4 text-gray-500 text-center">
                        <p>
                            <span className="font-semibold">Drag & Drop</span> your file or click <span className="font-semibold">Upload</span>
                        </p>
                        <p className="font-medium">Accepted file types: JPG, JPEG, or PNG.</p>
                    </div>
                )}
            </div>
            <input
                id="fileImageUpload"
                type="file"
                name="file"
                onChange={handleFileChange}
                accept=".png, .jpg, .jpeg"
                className="hidden"
                disabled={isLoading}
            />
            <div className="flex space-x-4 font-semibold w-full">
                <label
                    htmlFor="fileImageUpload"
                    className={`cursor-pointer py-2 px-4 rounded-lg text-center transition duration-300 border-2 border-green-700 hover:border-green-800 hover:bg-green-800 w-full
                        ${fileUrl ? "text-green-700 hover:text-white" : "bg-green-700 text-white "}`}
                >
                    Upload
                </label>

                <label
                    onClick={() => generateAiImage(desc)}
                    className={`cursor-pointer py-2 px-4 rounded-lg text-center transition duration-300 border-2 border-green-700 hover:border-green-800 hover:bg-green-800 w-full
                        ${fileUrl ? "text-green-700 hover:text-white" : "bg-green-700 text-white "}`}
                    disabled={isLoading}
                >
                    {isLoading ? "Generating..." : "Generate"}
                </label>

                {fileUrl && (
                    <label
                        onClick={handleRemoveFile}
                        className="cursor-pointer border-2 border-red-600 text-red-600 py-2 px-4 rounded-lg text-center hover:bg-red-600 hover:text-white transition duration-300 w-full"
                    >
                        Remove
                    </label>
                )}
            </div>
        </section>
    );
}

export default ImageUpload;
