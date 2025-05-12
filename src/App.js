
import './App.css';
import  { Logo } from './Components/Logo';
import { Nav } from './Components/Nav';
import { Principal } from './Components/Principal';
import {FilterComponent} from './Components/FilterComponent';
import { TableComponent } from './Components/TableComponent';
import { DataTable } from './Components/DataTable';


function App() {
  return (
    <div className="App">
      <aside>
      <Logo/>
      <Nav/>
      </aside>
      <div className='principal'>
        <Principal/>
        <FilterComponent></FilterComponent>
      </div>
      <div>
      <TableComponent></TableComponent>
      <DataTable></DataTable>
      </div>
    </div>
  
  )

}
export default App;