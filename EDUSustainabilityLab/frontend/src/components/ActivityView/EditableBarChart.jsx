import React, { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

const MAX_SUM = 100;

export default function EditableBarChart({ activity, framework, value1, value2, value3 }) {
  const [data, setData] = useState([]);
  const [description, setDescription] = useState("");

  // Update data whenever activity or framework are updated
  useEffect(() => {
    if (framework === "Pillars") {
      setData([
        { name: "Environment", value: activity?.categories?.environment || 0 },
        { name: "Social", value: activity?.categories?.social || 0 },
        { name: "Economic", value: activity?.categories?.economic || 0 },
      ]);
      setDescription(activity?.categories?.pillarsObjective || "");
    } else {
      setData([
        { name: "Curiosity", value: activity?.categories?.curious || 0 },
        { name: "Connections", value: activity?.categories?.connection || 0 },
        { name: "Creating Val", value: activity?.categories?.create || 0 },
      ]);
      setDescription(activity?.categories?.targetEMObjective || "");
    }
  }, [activity, framework]);

  return (
    <div className="flex flex-col gap-6 w-full justify-center self-center p-6">
      {/* Title */}
      <h2 className="text-xl font-bold">{framework}</h2>

      <div className="flex flex-col gap-2">
        {/* Bar Char */}
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
            <XAxis dataKey="name" />
            <YAxis domain={[0, MAX_SUM]} width={30} />
            <Bar dataKey="value">
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

        {/* Input */}
        <div className="flex gap-20 md:gap-12 pl-8 self-center">
            {data.map((item, index) => (
            <div key={index} className="flex flex-col items-center">
                <span className="border p-2 w-16 text-center">{item.value}</span>
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
          readOnly
        />
      </div>
    </div>
  );
}
