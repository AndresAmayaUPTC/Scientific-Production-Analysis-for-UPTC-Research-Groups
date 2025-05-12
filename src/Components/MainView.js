import React from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import PowerBIReport from './PowerBIReport';
import '../App.css';

function MainView() {
  return (
    <div>
      <div className='App'>
      <header><Header></Header></header>
      <aside className='App_aside'>
      <Sidebar></Sidebar>
      </aside>
      <main className='App_main'>
      <PowerBIReport></PowerBIReport>
      </main>
    </div>
      
    </div>
  );
}

export default MainView;
