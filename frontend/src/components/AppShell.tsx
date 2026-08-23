import {
  AppShell as MantineAppShell,
  Avatar,
  Badge,
  Box,
  Group,
  NavLink,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'
import {
  IconChartPie,
  IconHistory,
  IconListCheck,
  IconLogout,
  IconSettings,
} from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useMediaQuery } from '@mantine/hooks'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { listUnsynced } from '../api/transactions'
import { useAuth } from '../context/AuthContext'

const tabs = [
  { path: '/overview', label: 'Overview', icon: IconChartPie },
  { path: '/review', label: 'Review', icon: IconListCheck },
  { path: '/activity', label: 'Activity', icon: IconHistory },
  { path: '/more', label: 'More', icon: IconSettings },
]

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const mobile = useMediaQuery('(max-width: 47.99em)')
  const { data: pending = [] } = useQuery({
    queryKey: ['pending'],
    queryFn: listUnsynced,
  })

  return (
    <MantineAppShell
      header={{ height: 64 }}
      navbar={{ width: 232, breakpoint: 'sm', collapsed: { mobile: true } }}
      footer={{ height: 72, collapsed: !mobile }}
      padding={{ base: 'md', sm: 'xl' }}
    >
      <MantineAppShell.Header>
        <Group h="100%" px={{ base: 'md', sm: 'xl' }} justify="space-between">
          <UnstyledButton onClick={() => navigate('/overview')} aria-label="Go to overview">
            <Group gap="sm">
              <img src="/icons/favicon-48x48.png" alt="" width={32} height={32} />
              <Text fw={800} size="lg">Split</Text>
            </Group>
          </UnstyledButton>
          <Group gap="sm">
            <Box visibleFrom="sm"><Text size="sm" c="dimmed">{user?.email}</Text></Box>
            <Avatar size="sm" radius="xl">{user?.email.slice(0, 1).toUpperCase()}</Avatar>
          </Group>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Navbar p="md" visibleFrom="sm">
        <Stack gap={6} h="100%">
          {tabs.map(tab => (
            <NavLink
              key={tab.path}
              active={location.pathname === tab.path}
              label={tab.label}
              leftSection={<tab.icon size={20} />}
              rightSection={tab.path === '/review' && pending.length > 0 ? <Badge size="sm">{pending.length}</Badge> : null}
              onClick={() => navigate(tab.path)}
              variant="light"
            />
          ))}
          <Box mt="auto">
            <NavLink label="Sign out" leftSection={<IconLogout size={20} />} onClick={logout} />
          </Box>
        </Stack>
      </MantineAppShell.Navbar>

      <MantineAppShell.Main>
        <Box maw={1040} mx="auto">{children}</Box>
      </MantineAppShell.Main>

      <MantineAppShell.Footer hiddenFrom="sm" className="mobile-tab-bar">
        <Group h="100%" gap={0} grow preventGrowOverflow={false}>
          {tabs.map(tab => {
            const active = location.pathname === tab.path
            return (
              <UnstyledButton
                key={tab.path}
                className={`mobile-tab ${active ? 'mobile-tab--active' : ''}`}
                onClick={() => navigate(tab.path)}
              >
                <Box pos="relative">
                  <tab.icon size={23} stroke={active ? 2.3 : 1.7} />
                  {tab.path === '/review' && pending.length > 0 && (
                    <span className="tab-badge">{pending.length}</span>
                  )}
                </Box>
                <Text size="xs" fw={active ? 700 : 500}>{tab.label}</Text>
              </UnstyledButton>
            )
          })}
        </Group>
      </MantineAppShell.Footer>
    </MantineAppShell>
  )
}
