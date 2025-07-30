export default function Details({ formData, setFormData, errors, setErrors }) {
    const handleChange = (e) => {
        setFormData((prevData) => ({
            ...prevData,
            [e.target.name]: e.target.value
        }));

        setErrors((prevErrors) => ({
            ...prevErrors,
            [e.target.name]: e.target.value ? "" : prevErrors[e.target.name],
        }));
    };

    return (
        <div className="flex flex-col justify-center bg-white rounded-lg shadow gap-5 w-full p-10">
            {/* First Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Education Level */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Education Level</label>
                    <select 
                        name="educationLevel" 
                        className={`p-2 rounded-lg border-2 bg-white text-black hover:bg-gray-100
                            ${errors.educationLevel ? "border-red-400" : "border-gray-300"}`}
                        value={formData.educationLevel} 
                        onChange={handleChange}
                    >
                        <option value="">None</option>
                        <option value="FR">First Year</option>
                        <option value="SO">Sophomore</option>
                        <option value="JR">Junior</option>
                        <option value="SR">Senior</option>
                        <option value="GA">Graduate</option>
                        <option value="CE">Continuing Education</option>
                    </select>
                    <div className="text-red-500 min-h-[20px]">{errors.educationLevel}</div>
                </div>
        
                {/* Target Discipline */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Target Discipline</label>
                    <select 
                        name="targetDiscipline"
                        className={`p-2 rounded-lg border-2 bg-white text-black hover:bg-gray-100
                            ${errors.targetDiscipline ? "border-red-400" : "border-gray-300"}`}
                        value={formData.targetDiscipline}
                        onChange={handleChange}
                    >
                        <option value="">None</option>
                        <option value="AG">Agriculture & Life Science</option>
                        <option value="DI">Design</option>
                        <option value="ED">Education</option>
                        <option value="EG">Engineering</option>
                        <option value="HU">Humanities & Social Sciences</option>
                        <option value="NR">Natural Resources</option>
                        <option value="MA">Management</option>
                        <option value="MD">Medicine</option>
                        <option value="SC">Science</option>
                        <option value="TX">Textiles</option>
                    </select>
                    <div className="text-red-500 min-h-[20px]">{errors.targetDiscipline}</div>
                </div>
            </div>

            {/* Second Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Class Size */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Class Size (Number)</label>
                    <select 
                        name="classSize"
                        className={`p-2 rounded-lg border-2 bg-white text-black hover:bg-gray-100
                            ${errors.classSize ? "border-red-400" : "border-gray-300"}`}
                        value={formData.classSize} 
                        onChange={handleChange}
                    >
                        <option value="">None</option>
                        <option value="SM">Less than 50</option>
                        <option value="ME">50 - 100</option>
                        <option value="LA">More than 100</option>
                    </select>
                    <div className="text-red-500 min-h-[20px]">{errors.classSize}</div>
                </div>

                {/* Duration */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Duration</label>
                    <select 
                        name="duration" 
                        className={`p-2 rounded-lg border-2 bg-white text-black hover:bg-gray-100
                            ${errors.duration? "border-red-400" : "border-gray-300"}`}
                        value={formData.duration} 
                        onChange={handleChange}
                    >
                        <option value="">None</option>
                        <option value="SH">Short - Half hour or less</option>
                        <option value="MD">Medium - Half hour to 4 hours</option>
                        <option value="LO">Long - More than 4 hours</option>
                        <option value="WE">Week-long Project</option>
                        <option value="SE">Semester-long Project</option>
                    </select>
                    <div className="text-red-500 min-h-[20px]">{errors.duration}</div>
                </div>
            </div>

            {/* Third Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Activity Type */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Activity Type</label>
                    <select 
                        name="activityType" 
                        className={`p-2 rounded-lg border-2 bg-white text-black hover:bg-gray-100
                            ${errors.activityType ? "border-red-400" : "border-gray-300"}`}
                        value={formData.activityType} 
                        onChange={handleChange}
                    >
                        <option value="">None</option>
                        <option value="MM">Micromoment</option>
                        <option value="JS">Jigsaw</option>
                        <option value="CS">Case Study</option>
                        <option value="ST">Storytelling</option>
                        <option value="PB">Problem Solving Studio / Problem-Based Learning</option>
                        <option value="SC">Structured Academic Controversy</option>
                        <option value="EL">Experiential Learning</option>
                        <option value="DT">Design Thinking</option>
                        <option value="FA">Field Activity</option>
                        <option value="LC">Laboratory Course</option>
                        <option value="RM">Reflection / Metacognition</option>
                        <option value="NA">Other</option>
                    </select>
                    <div className="text-red-500 min-h-[20px]">{errors.activityType}</div>
                </div>

                {/* Activity Format */}
                <div className="flex flex-col w-full">
                    <label className="font-semibold">Activity Format</label>
                    <select 
                        name="activityFormat" 
                        className={`p-2 rounded-lg border-2 bg-white text-black hover:bg-gray-100
                            ${errors.activityFormat ? "border-red-400" : "border-gray-300"}`}
                        value={formData.activityFormat} 
                        onChange={handleChange}
                    >
                        <option value="">None</option>
                        <option value="IP">In-Person</option>
                        <option value="VI">Virtual</option>
                        <option value="HY">Hybrid</option>
                    </select>
                    <div className="text-red-500 min-h-[20px]">{errors.activityFormat}</div>
                </div>
            </div>
        </div>
    );
}
