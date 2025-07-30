import { useState, useEffect } from "react";

function ImageView({ imageFileId }) {
    const [imageUrl, setImageUrl] = useState("");

    useEffect(() => {
        async function fetchImage() {
            try {
                const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/file-info/${imageFileId}/`);
                if (!response.ok) throw new Error("Failed to fetch image details");

                const data = await response.json();
                const fileExtension = data.file_type.toLowerCase();

                if (["png", "jpg", "jpeg"].includes(fileExtension)) {
                    setImageUrl(`${process.env.REACT_APP_BACKEND_URL}/api/download/${imageFileId}/`);
                }
            } catch (error) {
                console.error("Error fetching image info:", error);
            }
        }

        if (imageFileId) {
            fetchImage();
        }
    }, [imageFileId]);

    return (
        <section className="flex flex-col gap-4 items-center rounded-lg bg-white w-full justify-center self-center">
            <div className="w-full h-[350px] flex items-center justify-center overflow-hidden bg-gray-100 rounded-lg">
                {imageUrl ? (
                    <img 
                        src={imageUrl} 
                        alt="Activity" 
                        className="max-w-full max-h-full object-contain rounded-lg" 
                    />
                ) : (
                    <p className="text-gray-500 font-medium">Loading image...</p>
                )}
            </div>
        </section>
    );
}

export default ImageView;
