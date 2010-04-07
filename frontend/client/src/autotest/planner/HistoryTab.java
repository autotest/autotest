package autotest.planner;


public class HistoryTab {
    
    public static interface Display {
        // Not yet implemented
    }
    
    
    @SuppressWarnings("unused")
    private Display display;
    
    public void bindDisplay(Display display) {
        this.display = display;
    }
    
}
