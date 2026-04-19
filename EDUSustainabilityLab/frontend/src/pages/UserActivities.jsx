import { useState, useEffect } from "react";
import Card from "../components/Card";


const UserActivities = () => {
    const [list, setList] = useState([]);
    useEffect(() => {
        fetch(`${process.env.REACT_APP_BACKEND_URL}/api/own/`, {
            method: "GET",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.list)
            if (data && Array.isArray(data.list)) {
                setList(data.list);
            } else {
                console.error("Invalid data structure", data);
            }
        })
        .catch(error => console.error("Error fetching list:", error));
    }, []);

    return (
        <>
            <div className="flex flex-wrap justify-center gap-4 w-full">
                {list.map((activity, index) => (
                    <Card key={index} activity={activity} />
                ))}
            </div>
        </>
    );
};

export default UserActivities;
