import React, { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

const MAX_SUM = 100;

export default function EditableBarChart({ title, value1, value2, value3, frameworkData, setFrameworkData, description, setDescription }) {
  let initialData = [];
  if (title === 'Pillars') {
    initialData = [
      { name: value1, value: Math.round(frameworkData.Environment) },
      { name: value2, value: Math.round(frameworkData.Social) },
      { name: value3, value: Math.round(frameworkData.Economic) },
    ];
  } else {
    initialData = [
      { name: value1, value: Math.round(frameworkData.Curiosity) },
      { name: value2, value: Math.round(frameworkData.Connections) },
      { name: value3, value: Math.round(frameworkData["Creating Val"]) },
    ];
  }

  const [data, setData] = useState(initialData);
  const [draggingIndex, setDraggingIndex] = useState(null);

  // Calculate the available space for a given index
  const getAvailableSpace = (index) => {
    return MAX_SUM - data.reduce((sum, item, i) => (i !== index ? sum + item.value : sum), 0);
  };

  // Handle input change while ensuring integer values
  const handleInputChange = (index, event) => {
    let newValue = Math.round(Math.max(0, Number(event.target.value))); // Ensure integer
    let maxAllowed = getAvailableSpace(index);
    newValue = Math.min(newValue, maxAllowed);

    setFrameworkData((prevData) => ({
      ...prevData,
      [event.target.name]: newValue, // Ensure frameworkData also stores integer
    }));

    const newData = [...data];
    newData[index].value = newValue;
    setData(newData);
  };

  // Handle description change
  const handleChange = (e) => {
    setDescription(e.target.value);
  };

  // Handle dragging while enforcing sum constraint
  const handleMouseDown = (index) => {
    setDraggingIndex(index);
  };

  const handleMouseMove = (event) => {
    if (draggingIndex !== null) {
        let newValue = Math.round(Math.max(0, data[draggingIndex].value - event.movementY)); // Ensure integer
        let maxAllowed = getAvailableSpace(draggingIndex);
        newValue = Math.min(newValue, maxAllowed);

        const newData = [...data];
        newData[draggingIndex].value = newValue;
        setData(newData);

        // Sync changes to frameworkData
        setFrameworkData((prevData) => ({
            ...prevData,
            [newData[draggingIndex].name]: newValue, // Ensure frameworkData is also updated
        }));
    }
};


  const handleMouseUp = () => {
    setDraggingIndex(null);
  };

  return (
    <div onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} className="flex flex-col gap-6 w-full justify-center self-center p-6">
      {/* Title */}
      <h2 className="text-xl font-bold">{title}</h2>

      <div className="flex flex-col gap-2">
        {/* Bar Chart */}
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <XAxis dataKey="name" />
            <YAxis domain={[0, MAX_SUM]} width={30} />
            <Bar dataKey="value" cursor="pointer" onMouseDown={(data, index) => handleMouseDown(index)}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    entry.name === value1 ? "green" :
                    entry.name === value2 ? "blue" :
                    entry.name === value3 ? "red" :
                    "gray"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Input Fields */}
        <div className="flex gap-20 md:gap-12 pl-8 self-center">
          {data.map((item, index) => (
            <div key={index} className="flex flex-col items-center">
              <input
                type="number"
                value={item.value}
                name={item.name}
                onChange={(e) => handleInputChange(index, e)}
                className="border p-2 w-16 text-center"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Description */}
      <div className="flex flex-col">
        <label className="font-semibold">Description</label>
        <textarea
          name="description"
          className="p-2 rounded-lg border-2 border-gray-300 resize-none"
          placeholder="Enter description"
          rows="5"
          value={description}
          onChange={handleChange}
        />
      </div>
    </div>
  );
}
