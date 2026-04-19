import React, { useState, useEffect, useRef } from 'react';

function LinkModal({ isOpen, onClose, onSubmit }) {
    const [linkUrl, setLinkUrl] = useState('');

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
            <div className="bg-white p-6 rounded-lg shadow-xl">
                <h2 className="text-xl mb-4">Insert Link</h2>
                <input 
                    type="text" 
                    value={linkUrl}
                    onChange={(e) => setLinkUrl(e.target.value)}
                    placeholder="Enter URL"
                    className="w-full border p-2 mb-4"
                />
                <div className="flex justify-end space-x-2">
                    <button 
                        onClick={onClose} 
                        className="px-4 py-2 bg-gray-200 rounded"
                    >
                        Cancel
                    </button>
                    <button 
                        onClick={() => onSubmit(linkUrl)} 
                        className="px-4 py-2 bg-blue-500 text-white rounded"
                    >
                        Insert
                    </button>
                </div>
            </div>
        </div>
    );
}

function About() {
    const isLoggedIn = useRef(false);
    const [loggedInUser, setloggedInUser] = useState({userId:'', userType:''});
    const [isAdmin, setIsAdmin] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    
    // State to track which section is being edited
    const [editSection, setEditSection] = useState(null);
    const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
    const [selectedRange, setSelectedRange] = useState(null);
    const [selectedSection, setSelectedSection] = useState(null);
    
    // State to store editable content and track unsaved changes
    const [content, setContent] = useState({});
    const [originalContent, setOriginalContent] = useState({});
    const [unsavedSections, setUnsavedSections] = useState(new Set());
    
    // Initial data load - fetch content from Django API
    useEffect(() => {
        fetchContent();
    }, []);

    // Function to fetch content from the Django API
    const fetchContent = () => {
        setIsLoading(true);
        fetch(`${process.env.REACT_APP_BACKEND_URL}/api/about-content/`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
            credentials: "include"
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Failed to fetch content");
                }
                return response.json();
            })
            .then(data => {
                // If no data returned or empty object, set default content
                if (!data || Object.keys(data).length === 0) {
                    const defaultContent = {
                        section1: {
                            title: 'What is Sustainability EDULab?',
                            body: 'Sustainability EDULab has been designed and conceived as an exchange, educational platform for educators and instructors to share teaching and learning materials on the value tensions of sustainability.'
                        },
                        section2: {
                            title: 'What are value tensions?',
                            body: 'Value tensions occur when stakeholders have priorities or values that are in conflict. With respect to sustainability, value tensions may occur when unbalance or a lack of equilibrium between the three common pillars of sustainability exists.'
                        }
                    };
                    setContent(defaultContent);
                    setOriginalContent(JSON.parse(JSON.stringify(defaultContent)));
                } else {
                    setContent(data);
                    setOriginalContent(JSON.parse(JSON.stringify(data)));
                }
                setUnsavedSections(new Set());
                setIsLoading(false);
            })
            .catch(error => {
                console.error("Error fetching content:", error);
                setError("Failed to load content. Please try again later.");
                setIsLoading(false);
            });
    };

    // Check if user is logged in and is an admin
    useEffect(() => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/debuggingUser/", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
            credentials: "include"
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Network response was not ok");
                }
                return response.json();
            })
            .then(data => {
                console.log("User data:", data);
                isLoggedIn.current = true;
                
                // Check if groups is an array
                if (Array.isArray(data.groups)) {
                    setIsAdmin(data.groups.includes("Administrator"));
                    setloggedInUser({userId: data.message, userType: data.groups});
                } else {
                    // Handle as string
                    setIsAdmin(data.groups === "Administrator");
                    setloggedInUser({userId: data.message, userType: [data.groups]});
                }
            })
            .catch(error => {
                console.error("There was a problem with the fetch operation:", error);
            });
    }, []);

    // Formatting functions
    const applyFormatting = (command) => {
        document.execCommand(command, false, null);
    };

    const applyLink = (url) => {
        if (!selectedRange || !url) {
            setIsLinkModalOpen(false);
            return;
        }

        // Focus on the correct editor before inserting link
        const editorId = `${selectedSection}-${selectedRange.type === 'title' ? 'title' : 'body'}-editor`;
        const editorElement = document.getElementById(editorId);
        
        if (editorElement) {
            // Restore the selection
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(selectedRange.range);

            // Create a new anchor element with styling
            const link = document.createElement('a');
            link.href = url.startsWith('http') ? url : `https://${url}`;
            link.textContent = selectedRange.range.toString();
            
            // Add Tailwind CSS classes for link styling
            link.className = 'text-blue-600 hover:text-blue-800 underline hover:no-underline transition-colors duration-200';
            
            // Optional: Add target="_blank" for external links
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');

            // Replace the selected text with the link
            selectedRange.range.deleteContents();
            selectedRange.range.insertNode(link);
        }

        setIsLinkModalOpen(false);
        setSelectedRange(null);
        setSelectedSection(null);
    };

    // Get content from editable elements
    const getContentFromElements = (section) => {
        const titleElement = document.getElementById(`${section}-title-editor`);
        const bodyElement = document.getElementById(`${section}-body-editor`);
        
        if (titleElement && bodyElement) {
            return {
                title: titleElement.innerHTML,
                body: bodyElement.innerHTML
            };
        }
        
        return null;
    };

    // Save edited content to the server
    const saveContent = (section) => {
        const sectionContent = getContentFromElements(section);
        
        if (sectionContent) {
            // Update the content with the new section data
            const updatedContent = {
                ...content,
                [section]: sectionContent
            };
            
            // Set local state first for immediate UI update
            setContent(updatedContent);
            
            // Save to server
            fetch(`${process.env.REACT_APP_BACKEND_URL}/api/update-about-content/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "include",
                body: JSON.stringify(updatedContent)
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error("Failed to save content");
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.status === 'success') {
                        console.log("Content saved successfully");
                        // Update original content after successful save
                        setOriginalContent(JSON.parse(JSON.stringify(updatedContent)));
                        // Remove section from unsaved set
                        const newUnsaved = new Set(unsavedSections);
                        newUnsaved.delete(section);
                        setUnsavedSections(newUnsaved);
                    } else {
                        throw new Error(data.message || "Unknown error");
                    }
                })
                .catch(error => {
                    console.error("Error saving content:", error);
                    alert("Failed to save content. Please try again.");
                });
        }
        
        setEditSection(null);
    };

    // Add a new section to local state only
    const addSection = () => {
        console.log("Adding new section...");
        
        // Calculate the next section number based on existing sections
        const sectionKeys = Object.keys(content);
        const sectionNumbers = sectionKeys.map(key => parseInt(key.replace('section', '')));
        const nextSectionNumber = sectionNumbers.length > 0 ? Math.max(...sectionNumbers) + 1 : 1;
        const newSectionKey = `section${nextSectionNumber}`;
        
        // Create new section with default content
        const newSection = {
            title: "New Section Title",
            body: "New section content goes here."
        };
        
        // Create updated content with the new section
        const updatedContent = {
            ...content,
            [newSectionKey]: newSection
        };
        
        // Add section to local state only - will be saved when user clicks Save
        setContent(updatedContent);
        
        // Mark as unsaved
        const newUnsaved = new Set(unsavedSections);
        newUnsaved.add(newSectionKey);
        setUnsavedSections(newUnsaved);
        
        // Set to edit mode
        setEditSection(newSectionKey);
    };
    
    // Cancel editing function
    const cancelEditing = (sectionKey) => {
        // Check if this is an unsaved section
        if (unsavedSections.has(sectionKey)) {
            // Remove the section from content if it was never saved
            const updatedContent = { ...content };
            delete updatedContent[sectionKey];
            setContent(updatedContent);
            
            // Remove from unsaved sections
            const newUnsaved = new Set(unsavedSections);
            newUnsaved.delete(sectionKey);
            setUnsavedSections(newUnsaved);
        } else if (originalContent[sectionKey]) {
            // Revert to original content if section was previously saved
            const updatedContent = {
                ...content,
                [sectionKey]: { ...originalContent[sectionKey] }
            };
            setContent(updatedContent);
        }
        
        // Exit edit mode
        setEditSection(null);
    };
    
    // Remove a section
    const removeSection = (sectionKey) => {
        // Check if this is the last section
        if (Object.keys(content).length <= 1) {
            alert('At least one section must remain.');
            return;
        }
        
        // Create a copy of the content without the section to be removed
        const updatedContent = { ...content };
        delete updatedContent[sectionKey];
        
        // Update local state first
        setContent(updatedContent);
        
        // Save to server
        fetch(`${process.env.REACT_APP_BACKEND_URL}/api/update-about-content/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            credentials: "include",
            body: JSON.stringify(updatedContent)
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Failed to remove section");
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    console.log("Section removed successfully");
                    // Update original content
                    setOriginalContent(JSON.parse(JSON.stringify(updatedContent)));
                } else {
                    throw new Error(data.message || "Unknown error");
                }
            })
            .catch(error => {
                console.error("Error removing section:", error);
                alert("Failed to remove section. Please try again.");
                // Restore content on error
                setContent(JSON.parse(JSON.stringify(originalContent)));
            });
        
        // If we're currently editing the section being removed, reset editSection
        if (editSection === sectionKey) {
            setEditSection(null);
        }
    };

    // Render the toolbar
    const renderToolbar = (section) => {
        return (
            <div className="flex items-center p-2 mb-2 bg-gray-100 rounded border overflow-x-auto">
                <button onClick={() => applyFormatting('bold')} className="px-3 py-1 mx-1 bg-white border rounded hover:bg-gray-100">
                    <strong>B</strong>
                </button>
                <button onClick={() => applyFormatting('italic')} className="px-3 py-1 mx-1 bg-white border rounded hover:bg-gray-100">
                    <em>I</em>
                </button>
                <button onClick={() => applyFormatting('underline')} className="px-3 py-1 mx-1 bg-white border rounded hover:bg-gray-100">
                    <u>U</u>
                </button>
                <button 
                    onClick={() => {
                        const selection = window.getSelection();
                        if (selection.rangeCount > 0) {
                            const range = selection.getRangeAt(0);
                            
                            // Ensure some text is selected
                            if (!range.collapsed) {
                                setSelectedRange({
                                    range: range,
                                    type: document.activeElement.id.includes('title') ? 'title' : 'body'
                                });
                                setSelectedSection(section);
                                setIsLinkModalOpen(true);
                            } else {
                                alert('Please select some text to create a link');
                            }
                        }
                    }} 
                    className="px-3 py-1 mx-1 bg-white border rounded hover:bg-gray-100"
                >
                    Link
                </button>
            </div>
        );
    };

    // Render a section based on edit state
    const renderSection = (sectionKey, sectionData) => {
        const isEditing = editSection === sectionKey;
        const isUnsaved = unsavedSections.has(sectionKey);
        
        return (
            <div key={sectionKey} className='flex flex-col p-4 shadow-lg rounded-lg w-full max-w-md md:max-w-2xl bg-zinc-50 gap-2 self-center relative'>
                {isUnsaved && !isEditing && (
                    <div className="absolute top-2 right-2 bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">
                        Unsaved
                    </div>
                )}
                
                {isEditing ? (
                    <>
                        {renderToolbar(sectionKey)}
                        <div 
                            id={`${sectionKey}-title-editor`}
                            className='font-semibold text-xl border-b-2 border-b-green-700 p-1 focus:outline-none focus:bg-white'
                            contentEditable={true}
                            dangerouslySetInnerHTML={{ __html: sectionData.title }}
                        />
                        <div 
                            id={`${sectionKey}-body-editor`}
                            className='leading-7 p-1 focus:outline-none focus:bg-white'
                            contentEditable={true}
                            dangerouslySetInnerHTML={{ __html: sectionData.body }}
                        />
                        <div className="flex justify-end gap-2 mt-2">
                            <button 
                                onClick={() => cancelEditing(sectionKey)} 
                                className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300"
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={() => saveContent(sectionKey)} 
                                className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                            >
                                Save
                            </button>
                        </div>
                    </>
                ) : (
                    <>
                        <h1 className='font-semibold text-xl border-b-2 border-b-green-700' dangerouslySetInnerHTML={{ __html: sectionData.title }} />
                        <p className='leading-7' dangerouslySetInnerHTML={{ __html: sectionData.body }} />
                        
                        {isAdmin && (
                            <div className="flex justify-end gap-2 mt-2">
                                <button 
                                    onClick={() => setEditSection(sectionKey)} 
                                    className="px-3 py-1 bg-blue-500 text-white rounded-md hover:bg-blue-600"
                                >
                                    Edit
                                </button>
                                <button 
                                    onClick={() => removeSection(sectionKey)} 
                                    className="px-3 py-1 bg-red-500 text-white rounded-md hover:bg-red-600"
                                    aria-label={`Remove section ${sectionKey}`}
                                >
                                    Remove
                                </button>
                            </div>
                        )}
                    </>
                )}
            </div>
        );
    };

    // Get all section keys and sort them numerically
    const getSortedSectionKeys = () => {
        return Object.keys(content).sort((a, b) => {
            const numA = parseInt(a.replace('section', ''));
            const numB = parseInt(b.replace('section', ''));
            return numA - numB;
        });
    };

    // For debugging
    console.log("Admin status:", isAdmin);
    console.log("User type:", loggedInUser.userType);
    console.log("Unsaved sections:", [...unsavedSections]);

    // Show loading state
    if (isLoading) {
        return (
            <div className="flex justify-center items-center h-64">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-700 mx-auto"></div>
                    <p className="mt-4">Loading content...</p>
                </div>
            </div>
        );
    }

    // Show error state
    if (error) {
        return (
            <div className="flex justify-center items-center h-64">
                <div className="text-center text-red-600">
                    <p>{error}</p>
                    <button 
                        onClick={fetchContent} 
                        className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    return (
        <>
            <div className="flex flex-col justify-center gap-5 items-center md:items-stretched w-full">
                {getSortedSectionKeys().map(sectionKey => (
                    renderSection(sectionKey, content[sectionKey])
                ))}
                
                {isAdmin && (
                    <div className="flex justify-center mt-4">
                        <button 
                            onClick={addSection} 
                            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center"
                        >
                            <span className="mr-1">+</span> Add New Section
                        </button>
                    </div>
                )}
            </div>

            <LinkModal 
                isOpen={isLinkModalOpen}
                onClose={() => setIsLinkModalOpen(false)}
                onSubmit={applyLink}
            />

            {loggedInUser.userType[0] === 'Pending' && (
                <p>
                    Your Account Must Be Approved In Order to Use The Website
                </p>
            )}
        </>
    );
};

export default About;