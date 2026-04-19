import { Link } from "react-router-dom";
import ImageView from "./ActivityView/ImageView";

function Card({ activity }) {
    let pillar = "Balanced";
    let entrepreneurship = "Balanced";

    let pillarBgColor = "bg-gray-600";
    let entrepreneurshipBgColor = "bg-gray-600";

    const environment = activity?.categories?.environment || activity?.environment || 0;
    const social = activity?.categories?.social || activity?.social || 0;
    const economy = activity?.categories?.economic || activity?.economy ||0;
    
    const curiosity = activity?.categories?.curious || activity?.curiosity || 0;
    const connections = activity?.categories?.connection || activity?.connections || 0;
    const creatingVal = activity?.categories?.create || activity?.creatingVal || 0;
    
    // Determine dominate category
    if (Math.max(connections, creatingVal, curiosity) === connections) {
        entrepreneurship = 'Connections';
        entrepreneurshipBgColor = "bg-blue-600";
    } else if (Math.max(connections, creatingVal, curiosity) === curiosity) {
        entrepreneurship = 'Curiosity';
        entrepreneurshipBgColor = "bg-green-600";
    } else if (Math.max(connections, creatingVal, curiosity) === creatingVal) {
        entrepreneurship = "Creating Value"
        entrepreneurshipBgColor = "bg-red-600";
    }

    // Determine dominant category
    if (Math.max(economy, environment, social) === social) {
        pillar = 'Social';
        pillarBgColor = "bg-blue-600";
    } else if (Math.max(economy, environment, social) === economy) {
        pillar = 'Economy';
        pillarBgColor = "bg-red-600";
    } else if (Math.max(economy, environment, social) === environment) {
        pillar = "Environment";
        pillarBgColor = "bg-green-600";
    }

    let author = activity?.creator_name || "Current User"

    console.log(activity);

    return (
        <Link to={`/view/${activity.id}`} className="block w-[550px]">
            <div className="flex flex-col gap-4 p-4 bg-zinc-50 rounded-lg shadow-lg hover:scale-105 transition max-w-[550px] h-auto sm:h-[600px] flex-shrink-0">
                {/* Image */}
                <ImageView imageFileId={activity?.image_id} />

                {/* Basic Info */}
                <div className="flex flex-col gap-2 flex-grow text-left">
                    <p className="font-semibold text-2xl line-clamp-2 text-ellipsis overflow-hidden">
                        {activity?.title}
                    </p>
                    <p className="font-semibold">{author}</p>
                    <p className="line-clamp-3 text-ellipsis overflow-hidden">
                        {activity?.description}
                    </p>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-2">
                    <p className={`text-white font-semibold px-4 py-2 rounded-full ${pillarBgColor}`}>
                        {pillar}
                    </p>
                    <p className={`text-white font-semibold px-4 py-2 rounded-full ${entrepreneurshipBgColor}`}>
                        {entrepreneurship}
                    </p>
                </div>
            </div>
        </Link>

    );
}

export default Card;