import { useMatches, Outlet } from "react-router-dom";
import Header from "./Header";
import Footer from "./Footer";
import backgroundImage from "../../images/background.webp";

function Layout() {
    const matches = useMatches();
    const title = matches.find(match => match.handle)?.handle?.title || "Default Title";

    return (
        <>
            <title>{title}</title>
            <div className="flex flex-col min-h-screen">
                <Header />
                <main 
                    style={{ backgroundImage: `url(${backgroundImage})` }} 
                    className="flex-grow bg-cover bg-no-repeat bg-center bg-fixed flex relative"
                >
                    <div className="w-full flex flex-col items-center gap-10 my-32">
                        <div className="text-4xl font-semibold p-2 text-center">{title}</div>
                        <Outlet />
                    </div>
                </main>
                <Footer />
            </div>
        </>
    );
}

export default Layout;
