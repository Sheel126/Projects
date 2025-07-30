import { Link } from "react-router-dom";
import backgroundImage from "../images/background.webp";

function Splash() {
    return (
        <>
            <title>Splash</title>
            <div className="flex flex-col min-h-screen">
                <div 
                    style={{ backgroundImage: `url(${backgroundImage})` }} 
                    className="flex-grow bg-cover bg-no-repeat bg-center bg-fixed flex flex-col md:flex-row h-screen"
                >
                    <div className="flex flex-col lg:flex-row w-full h-full">
                        <div className="w-full h-1/2 lg:w-1/2 lg:h-full flex flex-col justify-center items-center bg-zinc-50">
                            <div className="flex flex-col gap-10 p-8">
                                <div className="text-5xl lg:text-6xl font-bold">
                                    <h1>Welcome to The</h1>
                                    <h1 className="text-green-700">SustainabilityEDU Lab</h1>
                                </div>
                                <p className="text-xl lg:text-2xl font-semibold">To get started, register or login today!</p>
                                {/* <Link 
                                    to="/about" 
                                    className="text-2xl font-semibold bg-green-700 hover:bg-green-800 text-white px-6 py-2 text-center block rounded-lg w-max"
                                >
                                    About
                                </Link> */}
                            </div>
                        </div>

                        <div className="w-full h-1/2 lg:w-1/2 lg:h-full flex flex-col justify-center items-center gap-8 bg-zinc-50 lg:bg-transparent">
                            <div className="flex flex-col justify-center items-center gap-12 lg:bg-zinc-50 lg:rounded-lg lg:shadow lg:px-20 lg:py-14 max-w-md w-full">
                                <h1 className="text-3xl lg:text-4xl font-bold text-center w-full">Join today.</h1>
                                <div className="flex flex-col gap-6 w-full max-w-sm">
                                    <Link 
                                        to="/register" 
                                        className="text-xl font-semibold bg-green-700 hover:bg-green-800 text-white px-4 py-2 text-center block rounded-full"
                                    >
                                        Register
                                    </Link>
                                    <Link 
                                        to="/login"
                                        className="text-xl font-semibold bg-green-700 hover:bg-green-800 text-white px-4 py-2 text-center block rounded-full"
                                    >
                                        Login
                                    </Link>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

export default Splash;
