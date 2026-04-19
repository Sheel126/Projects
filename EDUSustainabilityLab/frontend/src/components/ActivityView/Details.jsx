export default function Details({ activity }) {
    if (!activity) {
        return (
            <div className="flex flex-col justify-center bg-white rounded-lg shadow gap-5 w-full p-10">
                <p className="text-center text-gray-500">Loading activity details...</p>
            </div>
        );
    }

    const levels = Array.isArray(activity.levels) ? activity.levels : [activity.levels].filter(Boolean);
    const target = Array.isArray(activity.target) ? activity.target : [activity.target].filter(Boolean);
    const classSize = activity.classSize || "";
    const duration = activity.duration || "";
    const activityType = activity.activityType || "";
    const format = activity.format || "";

    // Mapping of all values stored in activity data and proper values to be printed
    const mappings = {
        // Education Level
        FR: "First Year",
        SO: "Sophomore",
        JR: "Junior",
        SR: "Senior",
        GA: "Graduate",
        CE: "Continuing Education",
    
        // Target Discipline
        AG: "Agriculture & Life Science",
        DI: "Design",
        ED: "Education",
        EG: "Engineering",
        HU: "Humanities & Social Sciences",
        NR: "Natural Resources",
        MA: "Management",
        MD: "Medicine",
        SC: "Science",
        TX: "Textiles",

        // Class Size
        SM: "Less than 50",
        ME: "50 - 100",
        LA: "More than 100",
    
        // Duration
        SH: "Short - Half hour or less",
        MD: "Medium - Half hour to 4 hours",
        LO: "Long - More than 4 hours",
        WE: "Week-long Project",
        SE: "Semester-long Project",
    
        // Activity Type
        MM: "Micromoment",
        JS: "Jigsaw",
        CS: "Case Study",
        ST: "Storytelling",
        PB: "Problem Solving Studio / Problem-Based Learning",
        SC: "Structured Academic Controversy",
        EL: "Experiential Learning",
        DT: "Design Thinking",
        FA: "Field Activity",
        LC: "Laboratory Course",
        RM: "Reflection / Metacognition",
        NA: "Other",
    
        // Activity Format
        IP: "In-Person",
        VI: "Virtual",
        HY: "Hybrid",
    };

    return (
        <div className="flex flex-col justify-center bg-white rounded-lg shadow gap-10 pb-14 w-full p-10">
            {/* First Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Education Level */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Education Level</label>
                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white text-black">
                        {levels.length > 0 ? levels.map(level => mappings[level] || level).join(", ") : "N/A"}
                    </p>
                </div>
        
                {/* Target Discipline */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Target Discipline</label>
                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white text-black">
                        {target.length > 0 ? target.map(t => mappings[t] || t).join(", ") : "N/A"}
                    </p>
                </div>
            </div>

            {/* Second Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Class Size */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Class Size (Number)</label>
                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white text-black">
                        {mappings[classSize] || "N/A"}
                    </p>
                </div>

                {/* Duration */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Duration</label>
                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white text-black">
                        {mappings[duration] || "N/A"}
                    </p>
                </div>
            </div>

            {/* Third Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Activity Type */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Activity Type</label>
                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white text-black">
                        {mappings[activityType] || "N/A"}
                    </p>
                </div>

                {/* Activity Format */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Activity Format</label>
                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white text-black">
                        {mappings[format] || "N/A"}
                    </p>
                </div>
            </div>
        </div>
    );
}
