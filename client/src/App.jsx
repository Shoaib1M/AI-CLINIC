import { Route, Routes } from 'react-router'
import { AppShell } from './components/layout/AppShell'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { PublicLayout } from './components/layout/PublicLayout'
import AppointmentDetails from './pages/AppointmentDetails'
import DoctorDashboard from './pages/DoctorDashboard'
import FrontDesk from './pages/FrontDesk'
import Home from './pages/Home'
import Login from './pages/Login'
import ModelInfo from './pages/ModelInfo'
import NewAppointment from './pages/NewAppointment'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Home />} />
        <Route path="model" element={<ModelInfo />} />
      </Route>
      <Route path="login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route element={<ProtectedRoute roles={['frontdesk']} />}>
            <Route path="frontdesk" element={<FrontDesk />} />
            <Route path="frontdesk/new" element={<NewAppointment />} />
          </Route>
          <Route element={<ProtectedRoute roles={['doctor']} />}>
            <Route path="doctor" element={<DoctorDashboard />} />
          </Route>
          <Route path="appointments/:id" element={<AppointmentDetails />} />
        </Route>
      </Route>

      <Route element={<PublicLayout />}>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
