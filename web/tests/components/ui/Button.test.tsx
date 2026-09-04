import { fireEvent, render, screen } from "@testing-library/react";
import { Plus } from "lucide-react";
import { Button } from "../src/components/ui/Button";

describe("Button component", () => {
  it("renders with default props", () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole("button", { name: /click me/i });
    expect(button).toBeInTheDocument();
  });

  it("renders with variant prop", () => {
    render(<Button variant="primary">Primary</Button>);
    const button = screen.getByRole("button", { name: /primary/i });
    expect(button).toBeInTheDocument();
  });

  it("renders with size prop", () => {
    render(<Button size="sm">Small</Button>);
    const button = screen.getByRole("button", { name: /small/i });
    expect(button).toBeInTheDocument();
  });

  it("renders with loading prop", () => {
    render(<Button loading>Loading</Button>);
    const button = screen.getByRole("button", { name: /loading/i });
    expect(button).toBeDisabled();
  });

  it("renders with icon prop", () => {
    render(<Button icon={<Plus size={14} />}>Save</Button>);
    const icon = screen.getByRole("img", { hidden: true });
    expect(icon).toBeInTheDocument();
  });

  it("renders with startIcon prop", () => {
    render(<Button startIcon={<Plus size={14} />}>Action</Button>);
    const startIcon = screen.getByRole("img", { hidden: true });
    expect(startIcon).toBeInTheDocument();
  });

  it("renders with endIcon prop", () => {
    render(<Button endIcon={<Plus size={14} />}>Action</Button>);
    const endIcon = screen.getByRole("img", { hidden: true });
    expect(endIcon).toBeInTheDocument();
  });

  it("handles click event", () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    fireEvent.click(screen.getByRole("button", { name: /click/i }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("renders disabled state", () => {
    render(<Button disabled>Disabled</Button>);
    const button = screen.getByRole("button", { name: /disabled/i });
    expect(button).toBeDisabled();
  });

  it("applies variant styles correctly", () => {
    render(<Button variant="danger">Danger</Button>);
    const button = screen.getByRole("button", { name: /danger/i });
    const classList = button.className.split(" ");
    expect(classList).toContain("bg-danger-500");
    expect(classList).toContain("text-danger-fg");
  });
});
