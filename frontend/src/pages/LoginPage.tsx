import { Button, Card, Center, Image, Stack, Text, Title } from '@mantine/core'
import { IconBrandGoogle } from '@tabler/icons-react'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && user) navigate('/overview', { replace: true })
  }, [user, loading, navigate])

  function signIn() {
    const base = import.meta.env.VITE_API_DIRECT_URL ?? import.meta.env.VITE_API_BASE_URL ?? ''
    const next = import.meta.env.DEV ? `?next=${encodeURIComponent(window.location.origin)}` : ''
    window.location.href = `${base}/auth/login${next}`
  }

  return (
    <Center mih="100dvh" p="md" className="login-background">
      <Card w="100%" maw={380} ta="center" p={36} radius="xl" shadow="md" withBorder>
        <Stack align="center" gap="sm">
          <Image src="/icons/icon-128x128.png" alt="" w={64} h={64} />
          <Title order={1}>Split</Title>
          <Text c="dimmed" mb="lg">Track shared expenses and settle up.</Text>
          <Button
            size="md"
            fullWidth
            leftSection={<IconBrandGoogle size={20} />}
            onClick={signIn}
          >
            Sign in with Google
          </Button>
        </Stack>
      </Card>
    </Center>
  )
}
