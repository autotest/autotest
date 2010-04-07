package autotest.planner;


public class TestViewTab {
    
    public static interface Display {
        // Not yet implemented
    }
    
    @SuppressWarnings("unused")
    private Display display;
    
    public void bindDisplay(Display display) {
        this.display = display;
    }
    
}
