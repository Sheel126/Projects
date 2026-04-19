import React, { useEffect, useRef, useState } from 'react';
import { Chart } from 'chart.js/auto';
import style from '../assets/activitySearch.module.css';
import { Link, useNavigate } from 'react-router-dom';

const ActivityList = ({ activities, maxActivities = 14 }) => {
  const navigate = useNavigate();

  const parseCategories = (categories) => {
    try {
      const parsedCategories = typeof categories === 'string'
        ? JSON.parse(categories)
        : categories;

      console.log("we can get here with some categories??", parsedCategories);

      const filteredCategories = Object.entries(parsedCategories)
        .filter((_, index) => index !== 0)
        .filter(([key]) => !key.includes('Objective'));

      const capitalizeKey = (key) =>
        key.toLowerCase().replace(/(?:^|\s|-)\S/g, (match) => match.toUpperCase());

      const formatCategories = (entries) =>
        entries.map(([key, value]) => `${capitalizeKey(key)}: ${value}`).join(', ');

      const firstGroup = filteredCategories.filter(([key]) =>
        ['environment', 'social', 'economic'].includes(key)
      );

      const secondGroup = filteredCategories.filter(([key]) =>
        ['curious', 'connection', 'create'].includes(key)
      );

      const calculateTotal = (group) => group.reduce((sum, [, value]) => sum + value, 0);
      
      const normalizedGroup = (group) => {
        const total = calculateTotal(group);
        return total ? group.map(([key, value]) => [key, (value / total) * 100]) : [];
      };

      return {
        chartData: {
          firstGroup: normalizedGroup(firstGroup),
          secondGroup: normalizedGroup(secondGroup),
        },
      };
    } catch (error) {
      console.error('Failed to parse categories:', error);
      return { chartData: {} };
    }
  };

  const StackedBarChart = ({ data }) => {
    const canvasRef = useRef(null);
    const chartInstance = useRef(null);
  
    useEffect(() => {
      if (chartInstance.current) {
        chartInstance.current.destroy(); // Destroy old chart instance
      }
  
      chartInstance.current = new Chart(canvasRef.current, {
        type: 'bar',
        data: {
          labels: [''],
          datasets: data.map(([key, value], index) => ({
            label: key,
            data: [value],
            backgroundColor: [
              '#FF5533',
              '#33AAFF',
              '#33FF55',
              '#FFCC00',
              '#C70033',
              '#900C3F',
            ][index % 6], // Cycle through colors
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y', // Makes the bar horizontal
          scales: {
            x: {
              stacked: true,
              beginAtZero: true,
              max: 100, // Ensure total adds up to 100
            },
            y: {
              stacked: true,
            },
          },
          plugins: {
            legend: {
              position: 'top',
            },
          },
        },
      });
  
      return () => {
        if (chartInstance.current) {
          chartInstance.current.destroy();
        }
      };
    }, [data]);
  
    return (
      <div style={{ width: '100%', height: '75px', marginBottom: '20px' }}>
        <canvas ref={canvasRef} />
      </div>
    );
  };

    return (
        <div className={style.listcontainer}>
            {activities.slice(0, maxActivities).map((activity, index) => {
                const parsedActivity = JSON.parse(activity);
                const { chartData } = parseCategories(parsedActivity.categories);

                return (
                    <Link to={`/view/${parsedActivity.id}`} key={index}>
                    <div className={style.item}>
                        <h2>{parsedActivity.name}</h2>
                        <p><strong>Description:</strong> {parsedActivity.description}</p>
                        <StackedBarChart data={chartData.firstGroup} />
                        <StackedBarChart data={chartData.secondGroup} />
                        <StackedBarChart data={chartData.remainingGroup} />
                    </div>
                    </Link>
                );
            })}
        </div>
    );
};

export default ActivityList;
